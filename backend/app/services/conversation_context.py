from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Message


@dataclass
class ContextBuildResult:
    messages: list[dict[str, Any]]
    input_tokens: int
    selected_message_count: int
    total_message_count: int
    total_history_tokens: int
    context_budget_tokens: int
    response_token_reserve: int
    db_query_ms: int
    context_build_ms: int
    token_count_ms: int
    history_enabled: bool
    summary_used: bool


def decode_message_content(raw_content: str) -> Any:
    try:
        if raw_content.startswith('['):
            parsed = json.loads(raw_content)
            if isinstance(parsed, list):
                return parsed
    except (json.JSONDecodeError, AttributeError):
        pass
    return raw_content


def estimate_content_tokens(content: Any) -> int:
    if isinstance(content, str):
        return max(1, math.ceil(len(content) / 4))

    if isinstance(content, list):
        total = 0
        for item in content:
            if not isinstance(item, dict):
                total += max(1, math.ceil(len(str(item)) / 4))
                continue

            item_type = item.get('type')
            if item_type == 'text':
                total += max(1, math.ceil(len(str(item.get('text', ''))) / 4))
            elif item_type == 'image_url':
                total += settings.image_token_cost
            else:
                total += max(1, math.ceil(len(json.dumps(item, ensure_ascii=False)) / 4))
        return max(1, total)

    return max(1, math.ceil(len(json.dumps(content, ensure_ascii=False)) / 4))


def estimate_message_tokens(role: str, content: Any) -> int:
    role_overhead = 4 + max(1, math.ceil(len(role) / 8))
    return role_overhead + estimate_content_tokens(content)


def estimate_text_tokens(text: str | None) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))


def _truncate_history_content(content: Any, max_chars: int) -> Any:
    if max_chars <= 0:
        return content

    if isinstance(content, str):
        if len(content) <= max_chars:
            return content
        return f"{content[:max_chars].rstrip()}..."

    if isinstance(content, list):
        truncated_items: list[Any] = []
        for item in content:
            if not isinstance(item, dict):
                truncated_items.append(item)
                continue

            if item.get('type') == 'text' and isinstance(item.get('text'), str):
                text_value = item['text']
                if len(text_value) > max_chars:
                    next_item = dict(item)
                    next_item['text'] = f"{text_value[:max_chars].rstrip()}..."
                    truncated_items.append(next_item)
                else:
                    truncated_items.append(item)
            else:
                truncated_items.append(item)
        return truncated_items

    return content


def load_messages_for_context(db: Session, conversation_id: int) -> tuple[list[Message], int]:
    started_at = time.perf_counter()
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc(), Message.id.asc())
        .all()
    )
    elapsed_ms = round((time.perf_counter() - started_at) * 1000)
    return messages, elapsed_ms


def _compute_context_budget(response_token_reserve: int, enable_context_history: bool) -> int:
    derived_budget = settings.model_context_limit - response_token_reserve
    configured_budget = settings.context_token_budget if settings.context_token_budget > 0 else derived_budget
    budget = max(settings.minimum_context_budget, min(configured_budget, derived_budget))

    if enable_context_history and settings.enable_dynamic_history_budget and settings.history_max_prompt_tokens > 0:
        budget = min(budget, settings.history_max_prompt_tokens)

    return budget


def normalize_messages(raw_messages: list[Message | dict[str, Any]]) -> tuple[list[dict[str, Any]], int, int]:
    token_started_at = time.perf_counter()
    normalized_messages: list[dict[str, Any]] = []
    total_history_tokens = 0

    for message in raw_messages:
        if isinstance(message, dict):
            content = message.get('content')
            if isinstance(content, str):
                content = decode_message_content(content)
            token_count = int(message.get('tokens') or estimate_message_tokens(str(message.get('role', 'user')), content))
            message_id = int(message.get('id', 0))
            role = str(message.get('role', 'user'))
        else:
            content = decode_message_content(message.content)
            token_count = estimate_message_tokens(message.role, content)
            message_id = message.id
            role = message.role

        normalized_messages.append({
            'id': message_id,
            'role': role,
            'content': content,
            'tokens': token_count,
        })
        total_history_tokens += token_count

    token_count_ms = round((time.perf_counter() - token_started_at) * 1000)
    return normalized_messages, total_history_tokens, token_count_ms


def build_conversation_context_from_messages(
    raw_messages: list[Message],
    system_prompt: str | None,
    response_token_reserve: int,
    enable_context_history: bool,
    summary_text: str | None = None,
    summary_covered_until_message_id: int | None = None,
    db_query_ms: int = 0,
) -> ContextBuildResult:
    normalized_messages, total_history_tokens, token_count_ms = normalize_messages(raw_messages)

    context_started_at = time.perf_counter()
    context_budget_tokens = _compute_context_budget(response_token_reserve, enable_context_history)

    messages_for_model: list[dict[str, Any]] = []
    consumed_tokens = 0
    system_tokens = estimate_text_tokens(system_prompt) + 4 if system_prompt else 0
    if system_prompt:
        messages_for_model.append({'role': 'system', 'content': system_prompt})
        consumed_tokens += system_tokens

    summary_used = False
    if summary_text:
        summary_message = {
            'role': 'system',
            'content': f'Resumen previo de la conversación:\n{summary_text}',
        }
        summary_tokens = estimate_message_tokens(summary_message['role'], summary_message['content'])
        if consumed_tokens + summary_tokens <= context_budget_tokens:
            messages_for_model.append(summary_message)
            consumed_tokens += summary_tokens
            summary_used = True

    candidate_messages = normalized_messages
    if summary_used and summary_covered_until_message_id is not None:
        candidate_messages = [
            message for message in normalized_messages if message['id'] > summary_covered_until_message_id
        ]

    selected_messages: list[dict[str, Any]] = []
    if candidate_messages:
        latest_message = candidate_messages[-1]
        latest_tokens = latest_message['tokens']
        if consumed_tokens + latest_tokens <= context_budget_tokens:
            selected_messages.append({
                'role': latest_message['role'],
                'content': latest_message['content'],
            })
            consumed_tokens += latest_tokens
        else:
            selected_messages.append({
                'role': latest_message['role'],
                'content': latest_message['content'],
            })
            consumed_tokens = context_budget_tokens

        if enable_context_history:
            additional_messages = 0
            additional_tokens = 0
            max_additional_messages = max(0, settings.history_recent_messages_cap)
            max_additional_tokens = max(0, settings.history_recent_tokens_cap)
            max_message_chars = max(0, settings.history_message_char_cap)

            for message in reversed(candidate_messages[:-1]):
                if not settings.history_include_assistant_messages and message['role'] == 'assistant':
                    continue

                if max_additional_messages > 0 and additional_messages >= max_additional_messages:
                    break

                truncated_content = _truncate_history_content(message['content'], max_message_chars)
                message_tokens = estimate_message_tokens(message['role'], truncated_content)

                projected_additional_tokens = additional_tokens + message_tokens
                if max_additional_tokens > 0 and projected_additional_tokens > max_additional_tokens:
                    break

                projected_tokens = consumed_tokens + message_tokens
                if projected_tokens > context_budget_tokens:
                    break

                selected_messages.insert(0, {
                    'role': message['role'],
                    'content': truncated_content,
                })
                consumed_tokens = projected_tokens
                additional_messages += 1
                additional_tokens = projected_additional_tokens

    messages_for_model.extend(selected_messages)
    context_build_ms = round((time.perf_counter() - context_started_at) * 1000)

    return ContextBuildResult(
        messages=messages_for_model,
        input_tokens=consumed_tokens,
        selected_message_count=len(selected_messages),
        total_message_count=len(normalized_messages),
        total_history_tokens=total_history_tokens,
        context_budget_tokens=context_budget_tokens,
        response_token_reserve=response_token_reserve,
        db_query_ms=db_query_ms,
        context_build_ms=context_build_ms,
        token_count_ms=token_count_ms,
        history_enabled=enable_context_history,
        summary_used=summary_used,
    )


def build_conversation_context(
    db: Session,
    conversation_id: int,
    system_prompt: str | None,
    response_token_reserve: int,
    enable_context_history: bool,
    summary_text: str | None = None,
    summary_covered_until_message_id: int | None = None,
) -> ContextBuildResult:
    raw_messages, db_query_ms = load_messages_for_context(db, conversation_id)
    return build_conversation_context_from_messages(
        raw_messages,
        system_prompt,
        response_token_reserve,
        enable_context_history,
        summary_text=summary_text,
        summary_covered_until_message_id=summary_covered_until_message_id,
        db_query_ms=db_query_ms,
    )