from datetime import datetime
from typing import Generator, Optional

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
    build_chat_history,
    get_provider_url,
    get_recent_messages,
    build_model_payload,
    stream_provider_response,
    save_assistant_message,
)

router = APIRouter()


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
    return message


@router.post('/{conversation_id}/chat')
def chat(
    conversation_id: int,
    chat_request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    if chat_request.role != 'user':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Only user messages are supported for chat')

    conversation = get_user_conversation(db, conversation_id, current_user.id)

    user_message = Message(
        conversation_id=conversation.id,
        role='user',
        content=chat_request.content,
    )
    db.add(user_message)
    conversation.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user_message)

    max_context_messages = chat_request.max_context_messages or settings.max_context_messages
    
    # If context history is disabled, only get the current message (no previous context)
    if chat_request.enable_context_history is False:
        max_context_messages = 1
    else:
        # Limit to 15 messages when context history is enabled
        max_context_messages = min(max_context_messages, 15)
    
    recent_messages = get_recent_messages(db, conversation.id, max_context_messages)
    messages = build_chat_history(recent_messages, settings.system_prompt)

    provider_name = chat_request.provider or getattr(current_user.preferences, 'default_provider', 'liteRT')
    model_name = chat_request.model or getattr(current_user.preferences, 'default_model', None)
    temperature = chat_request.temperature if chat_request.temperature is not None else getattr(current_user.preferences, 'temperature', 0.7)
    max_tokens = chat_request.max_tokens if chat_request.max_tokens is not None else getattr(current_user.preferences, 'context_length', None)

    payload = build_model_payload(provider_name, model_name, temperature, max_tokens, messages)
    provider_url = get_provider_url(provider_name)
    assistant_parts: list[str] = []

    def event_stream() -> Generator[bytes, None, None]:
        for chunk in stream_provider_response(provider_url, payload, assistant_parts):
            yield chunk

        assistant_text = ''.join(assistant_parts).strip()
        if assistant_text:
            save_assistant_message(db, conversation.id, assistant_text)
            conversation.updated_at = datetime.utcnow()
            db.commit()

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
    return Response(status_code=status.HTTP_204_NO_CONTENT)
