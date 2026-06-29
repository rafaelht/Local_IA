from datetime import datetime
from typing import Generator, Optional
import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.v1.routes.auth import get_current_user
from app.core.config import settings
from app.db.models import Conversation, Message, User
from app.db.session import get_db
from app.schemas.conversation import (
    ChatRequest,
    ConversationCreate,
    ConversationRead,
    ConversationUpdate,
    MessageCreate,
    MessageRead,
)
from app.services.chat import (
    build_model_payload,
    resolve_provider_model,
    stream_provider_response,
    save_assistant_message,
)
from app.services.conversation_context import build_conversation_context_from_messages, estimate_text_tokens, load_messages_for_context
from app.services.conversation_cache import active_conversation_cache
from app.services.conversation_summary import maybe_refresh_conversation_summary
from app.services.conversation_summary import SummaryRefreshResult
from app.services.conversation_summary import get_conversation_summary_state
from app.services.litert_conversation_manager import litert_conversation_manager


logger = logging.getLogger(__name__)

router = APIRouter()


def build_metrics_event(phase: str, metrics: dict[str, int | float | bool | None]) -> bytes:
    payload = {
        'type': 'metrics',
        'phase': phase,
        'metrics': metrics,
    }
    return f"event: metrics\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n".encode('utf-8')


def get_user_conversation(db: Session, conversation_id: int, user_id: int) -> Conversation:
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Conversación no encontrada')
    return conversation


@router.get('', response_model=list[ConversationRead])
def list_conversations(
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Conversation]:
    query = db.query(Conversation).filter(Conversation.user_id == current_user.id)
    if search:
        query = query.filter(
            Conversation.title.ilike(f"%{search}%") |
            Conversation.messages.any(Message.content.ilike(f"%{search}%"))
        )
    return (
        query.order_by(Conversation.pinned.desc(), Conversation.updated_at.desc())
        .all()
    )


@router.post('', response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
def create_conversation(
    conversation_in: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Conversation:
    title = conversation_in.title or 'Nueva conversación'
    conversation = Conversation(title=title, user_id=current_user.id)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get('/{conversation_id}', response_model=ConversationRead)
def get_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Conversation:
    return get_user_conversation(db, conversation_id, current_user.id)


@router.put('/{conversation_id}', response_model=ConversationRead)
def update_conversation(
    conversation_id: int,
    conversation_update: ConversationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Conversation:
    conversation = get_user_conversation(db, conversation_id, current_user.id)
    if conversation_update.title is not None:
        conversation.title = conversation_update.title
    if conversation_update.pinned is not None:
        conversation.pinned = conversation_update.pinned
    if conversation_update.favorite is not None:
        conversation.favorite = conversation_update.favorite
    conversation.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(conversation)
    return conversation


@router.delete('/{conversation_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    conversation = get_user_conversation(db, conversation_id, current_user.id)
    db.delete(conversation)
    db.commit()
    active_conversation_cache.invalidate(conversation.id)
    litert_conversation_manager.invalidate(conversation.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post('/{conversation_id}/messages', response_model=MessageRead, status_code=status.HTTP_201_CREATED)
def create_message(
    conversation_id: int,
    message_in: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Message:
    conversation = get_user_conversation(db, conversation_id, current_user.id)
    message = Message(
        conversation_id=conversation.id,
        role=message_in.role,
        content=message_in.content,
    )
    db.add(message)
    conversation.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(message)
    active_conversation_cache.invalidate(conversation.id)
    litert_conversation_manager.invalidate(conversation.id)
    return message


@router.post('/{conversation_id}/chat')
def chat(
    conversation_id: int,
    chat_request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    request_started_at = time.perf_counter()
    if chat_request.role != 'user':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Only user messages are supported for chat')

    conversation = get_user_conversation(db, conversation_id, current_user.id)

    user_request_content = chat_request.content

    # Convert content to JSON string for DB persistence when it's multimodal input.
    message_content = user_request_content
    if isinstance(user_request_content, list):
        message_content = json.dumps(user_request_content, ensure_ascii=False)

    user_message = Message(
        conversation_id=conversation.id,
        role='user',
        content=message_content,
    )
    db_write_started_at = time.perf_counter()
    db.add(user_message)
    conversation.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user_message)
    db_write_ms = round((time.perf_counter() - db_write_started_at) * 1000)

    provider_name = chat_request.provider or getattr(current_user.preferences, 'default_provider', 'liteRT')
    model_name = chat_request.model or getattr(current_user.preferences, 'default_model', None)
    try:
        resolved_model_name = resolve_provider_model(provider_name, model_name, current_user.preferences)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    temperature = chat_request.temperature if chat_request.temperature is not None else getattr(current_user.preferences, 'temperature', 0.7)
    response_token_reserve = chat_request.max_tokens if chat_request.max_tokens is not None else getattr(current_user.preferences, 'context_length', settings.response_token_reserve)

    cache_hit = False
    cached_state = active_conversation_cache.get(conversation.id)
    if cached_state is not None:
        raw_messages = cached_state.messages
        db_query_ms = 0
        cache_hit = True
    else:
        raw_messages, db_query_ms = load_messages_for_context(db, conversation.id)

    if cache_hit:
        raw_messages = [
            *raw_messages,
            {
                'id': user_message.id,
                'role': user_message.role,
                'content': user_message.content,
            },
        ]

    history_enabled = chat_request.enable_context_history is not False
    use_litert_sdk = provider_name == 'liteRT' and settings.litert_sdk_enabled

    if history_enabled and settings.history_response_token_cap > 0:
        response_token_reserve = min(response_token_reserve, settings.history_response_token_cap)

    def prepare_http_inference_state() -> tuple[SummaryRefreshResult, object, dict]:
        if history_enabled and settings.enable_conversation_summary:
            summary_threshold_reached = len(raw_messages) >= settings.summary_trigger_messages
            if settings.summary_in_request_path:
                if summary_threshold_reached:
                    summary_result_local = maybe_refresh_conversation_summary(
                        db,
                        conversation.id,
                        raw_messages,
                        provider_name,
                        current_user.preferences,
                        model_name,
                        temperature,
                    )
                else:
                    summary_result_local = SummaryRefreshResult(
                        summary_text=None,
                        covered_until_message_id=None,
                        summary_generation_ms=0,
                        summary_used=False,
                    )
            else:
                if summary_threshold_reached:
                    summary_result_local = get_conversation_summary_state(db, conversation.id)
                else:
                    summary_result_local = SummaryRefreshResult(
                        summary_text=None,
                        covered_until_message_id=None,
                        summary_generation_ms=0,
                        summary_used=False,
                    )
        else:
            summary_result_local = SummaryRefreshResult(
                summary_text=None,
                covered_until_message_id=None,
                summary_generation_ms=0,
                summary_used=False,
            )

        if cache_hit:
            active_conversation_cache.update_summary(
                conversation.id,
                summary_result_local.summary_text,
                summary_result_local.covered_until_message_id,
            )

        context_result_local = build_conversation_context_from_messages(
            raw_messages,
            settings.system_prompt,
            response_token_reserve=response_token_reserve,
            enable_context_history=history_enabled,
            summary_text=summary_result_local.summary_text,
            summary_covered_until_message_id=summary_result_local.covered_until_message_id,
            db_query_ms=db_query_ms,
        )

        payload_local = build_model_payload(
            provider_name,
            resolved_model_name,
            temperature,
            response_token_reserve,
            context_result_local.messages,
        )
        return summary_result_local, context_result_local, payload_local

    if use_litert_sdk:
        summary_result = SummaryRefreshResult(
            summary_text=None,
            covered_until_message_id=None,
            summary_generation_ms=0,
            summary_used=False,
        )
        context_result = None
        payload = None
    else:
        summary_result, context_result, payload = prepare_http_inference_state()

    assistant_parts: list[str] = []
    if use_litert_sdk:
        metrics: dict[str, int | float | bool | None] = {
            'db_write_ms': db_write_ms,
            'db_query_ms': db_query_ms,
            'context_build_ms': 0,
            'token_count_ms': 0,
            'model_call_ms': None,
            'prefill_ms': None,
            'ttft_ms': None,
            'generation_tokens_per_sec': None,
            'input_tokens': 0,
            'output_tokens': 0,
            'selected_message_count': len(raw_messages),
            'context_budget_tokens': 0,
            'response_token_reserve': response_token_reserve,
            'history_enabled': history_enabled,
            'summary_used': False,
            'summary_generation_ms': 0,
            'total_message_count': len(raw_messages),
            'total_history_tokens': 0,
            'cache_hit': cache_hit,
            'litert_runtime_reused': None,
            'litert_hydration_ms': None,
            'litert_http_fallback': False,
        }
    else:
        metrics = {
            'db_write_ms': db_write_ms,
            'db_query_ms': context_result.db_query_ms,
            'context_build_ms': context_result.context_build_ms,
            'token_count_ms': context_result.token_count_ms,
            'model_call_ms': None,
            'prefill_ms': None,
            'ttft_ms': None,
            'generation_tokens_per_sec': None,
            'input_tokens': context_result.input_tokens,
            'output_tokens': 0,
            'selected_message_count': context_result.selected_message_count,
            'context_budget_tokens': context_result.context_budget_tokens,
            'response_token_reserve': context_result.response_token_reserve,
            'history_enabled': context_result.history_enabled,
            'summary_used': context_result.summary_used,
            'summary_generation_ms': summary_result.summary_generation_ms,
            'total_message_count': context_result.total_message_count,
            'total_history_tokens': context_result.total_history_tokens,
            'cache_hit': cache_hit,
        }

    def event_stream() -> Generator[bytes, None, None]:
        model_call_started_at = time.perf_counter()
        first_token_at: float | None = None

        yield build_metrics_event('context_ready', metrics)

        def mark_first_token() -> None:
            nonlocal first_token_at
            if first_token_at is None:
                first_token_at = time.perf_counter()
                metrics['prefill_ms'] = round((first_token_at - model_call_started_at) * 1000)
                metrics['ttft_ms'] = round((first_token_at - request_started_at) * 1000)

        try:
            if use_litert_sdk:
                stream_iter, sdk_metadata = litert_conversation_manager.stream_message(
                    conversation_id=conversation.id,
                    user_message_content=user_request_content if user_request_content is not None else message_content,
                    history_messages=raw_messages,
                    current_user_message_id=user_message.id,
                    model_name=resolved_model_name,
                    system_prompt=settings.system_prompt,
                    temperature=temperature,
                )
                metrics['litert_runtime_reused'] = bool(sdk_metadata.get('reused_runtime'))
                metrics['litert_hydration_ms'] = int(sdk_metadata.get('hydration_ms') or 0)
                metrics['litert_active_conversations'] = int(sdk_metadata.get('active_conversations') or 0)

                sdk_emitted_any = False
                for text_chunk in stream_iter:
                    if text_chunk and first_token_at is None:
                        mark_first_token()
                    assistant_parts.append(text_chunk)
                    sdk_emitted_any = True
                    chunk_payload = {
                        'choices': [
                            {
                                'delta': {
                                    'content': text_chunk,
                                }
                            }
                        ]
                    }
                    yield f"data: {json.dumps(chunk_payload, ensure_ascii=False)}\n\n".encode('utf-8')

                yield b'data: [DONE]\n\n'
            else:
                for chunk in stream_provider_response(
                    provider_name,
                    current_user.preferences,
                    payload,
                    assistant_parts,
                    on_first_token=mark_first_token,
                ):
                    yield chunk
        except RuntimeError as exc:
            if use_litert_sdk and settings.litert_sdk_fallback_to_http and not assistant_parts:
                litert_conversation_manager.mark_http_fallback()
                metrics['litert_http_fallback'] = True

                summary_result_http, context_result_http, payload_http = prepare_http_inference_state()
                metrics['db_query_ms'] = context_result_http.db_query_ms
                metrics['context_build_ms'] = context_result_http.context_build_ms
                metrics['token_count_ms'] = context_result_http.token_count_ms
                metrics['input_tokens'] = context_result_http.input_tokens
                metrics['selected_message_count'] = context_result_http.selected_message_count
                metrics['context_budget_tokens'] = context_result_http.context_budget_tokens
                metrics['response_token_reserve'] = context_result_http.response_token_reserve
                metrics['history_enabled'] = context_result_http.history_enabled
                metrics['summary_used'] = context_result_http.summary_used
                metrics['summary_generation_ms'] = summary_result_http.summary_generation_ms
                metrics['total_message_count'] = context_result_http.total_message_count
                metrics['total_history_tokens'] = context_result_http.total_history_tokens
                yield build_metrics_event('context_ready', metrics)

                for chunk in stream_provider_response(
                    provider_name,
                    current_user.preferences,
                    payload_http,
                    assistant_parts,
                    on_first_token=mark_first_token,
                ):
                    yield chunk
                return

            error_text = f'Error del proveedor: {exc}'
            assistant_parts.append(error_text)
            error_payload = {
                'choices': [
                    {
                        'delta': {
                            'content': error_text,
                        }
                    }
                ]
            }
            yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n".encode('utf-8')
            yield b'data: [DONE]\n\n'
        finally:
            model_call_finished_at = time.perf_counter()
            metrics['model_call_ms'] = round((model_call_finished_at - model_call_started_at) * 1000)
            output_text = ''.join(assistant_parts)
            output_tokens = estimate_text_tokens(output_text)
            metrics['output_tokens'] = output_tokens
            if first_token_at is not None:
                generation_window_ms = max(1, round((model_call_finished_at - first_token_at) * 1000))
                metrics['generation_tokens_per_sec'] = round(output_tokens / (generation_window_ms / 1000), 2)

        assistant_text = ''.join(assistant_parts).strip()
        saved_assistant = None
        if assistant_text:
            saved_assistant = save_assistant_message(db, conversation.id, assistant_text)
            conversation.updated_at = datetime.utcnow()
            db.commit()

            if (
                not use_litert_sdk
                and history_enabled
                and settings.enable_conversation_summary
                and not settings.summary_in_request_path
            ):
                summary_source_messages = [*raw_messages, {
                    'id': saved_assistant.id,
                    'role': saved_assistant.role,
                    'content': saved_assistant.content,
                }]
                try:
                    maybe_refresh_conversation_summary(
                        db,
                        conversation.id,
                        summary_source_messages,
                        provider_name,
                        current_user.preferences,
                        resolved_model_name,
                        temperature,
                    )
                except RuntimeError:
                    logger.warning('deferred_summary_refresh_failed', exc_info=True)

        if cache_hit:
            active_conversation_cache.update_message(conversation.id, user_message.id, user_message.role, user_message.content)
            if saved_assistant is not None:
                active_conversation_cache.update_message(
                    conversation.id,
                    saved_assistant.id,
                    saved_assistant.role,
                    saved_assistant.content,
                )
        else:
            cache_messages = list(raw_messages)
            if saved_assistant is not None:
                cache_messages.append(
                    {
                        'id': saved_assistant.id,
                        'role': saved_assistant.role,
                        'content': saved_assistant.content,
                    }
                )
            active_conversation_cache.set(
                conversation.id,
                cache_messages,
                summary_text=summary_result.summary_text,
                summary_covered_until_message_id=summary_result.covered_until_message_id,
            )

        logger.info(
            'chat_metrics %s',
            json.dumps(
                {
                    'conversation_id': conversation.id,
                    'provider': provider_name,
                    'model': model_name,
                    **metrics,
                },
                ensure_ascii=False,
            ),
        )
        yield build_metrics_event('completed', metrics)

    return StreamingResponse(event_stream(), media_type='text/event-stream')


@router.delete('/{conversation_id}/messages/{message_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_message(
    conversation_id: int,
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    conversation = get_user_conversation(db, conversation_id, current_user.id)
    message = (
        db.query(Message)
        .filter(Message.id == message_id, Message.conversation_id == conversation.id)
        .first()
    )
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Mensaje no encontrado')
    db.delete(message)
    db.commit()
    active_conversation_cache.remove_message(conversation.id, message.id)
    litert_conversation_manager.invalidate(conversation.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
