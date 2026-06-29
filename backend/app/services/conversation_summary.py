from __future__ import annotations

import json
import time
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import ConversationSummary, Message
from app.services.chat import generate_provider_completion
from app.services.conversation_context import (
    estimate_message_tokens,
    estimate_text_tokens,
    normalize_messages,
)


@dataclass
class SummaryRefreshResult:
    summary_text: str | None
    covered_until_message_id: int | None
    summary_generation_ms: int
    summary_used: bool


def _stringify_message_content(content: object) -> str:
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=False)


def _build_summary_prompt(existing_summary: str | None, messages_to_cover: list[dict]) -> list[dict]:
    transcript_lines: list[str] = []
    for message in messages_to_cover:
        transcript_lines.append(f"{message['role'].upper()}: {_stringify_message_content(message['content'])}")

    instructions = (
        'Resume la conversación preservando decisiones, datos, pendientes, restricciones y contexto técnico útil. '
        'No inventes información. Devuelve un resumen compacto en español.'
    )

    if existing_summary:
        user_prompt = (
            f"Resumen previo:\n{existing_summary}\n\n"
            f"Actualiza ese resumen con estos mensajes nuevos:\n\n{'\n'.join(transcript_lines)}"
        )
    else:
        user_prompt = f"Resume estos mensajes de la conversación:\n\n{'\n'.join(transcript_lines)}"

    return [
        {'role': 'system', 'content': instructions},
        {'role': 'user', 'content': user_prompt},
    ]


def maybe_refresh_conversation_summary(
    db: Session,
    conversation_id: int,
    raw_messages: list[Message],
    provider_name: str,
    preferences: object | None,
    model_name: str | None,
    temperature: float,
) -> SummaryRefreshResult:
    normalized_messages, total_history_tokens, _token_count_ms = normalize_messages(raw_messages)
    existing_summary = (
        db.query(ConversationSummary)
        .filter(ConversationSummary.conversation_id == conversation_id)
        .first()
    )

    threshold_exceeded = (
        len(normalized_messages) >= settings.summary_trigger_messages
        or total_history_tokens >= settings.summary_trigger_tokens
    )
    if not threshold_exceeded:
        return SummaryRefreshResult(
            summary_text=existing_summary.summary_text if existing_summary else None,
            covered_until_message_id=existing_summary.covered_until_message_id if existing_summary else None,
            summary_generation_ms=0,
            summary_used=existing_summary is not None,
        )

    cutoff_index = max(0, len(normalized_messages) - settings.summary_keep_recent_messages)
    messages_eligible = normalized_messages[:cutoff_index]
    if not messages_eligible:
        return SummaryRefreshResult(
            summary_text=existing_summary.summary_text if existing_summary else None,
            covered_until_message_id=existing_summary.covered_until_message_id if existing_summary else None,
            summary_generation_ms=0,
            summary_used=existing_summary is not None,
        )

    if existing_summary:
        messages_to_cover = [
            message for message in messages_eligible if message['id'] > existing_summary.covered_until_message_id
        ]
        summary_seed = existing_summary.summary_text
    else:
        messages_to_cover = messages_eligible
        summary_seed = None

    if not messages_to_cover:
        return SummaryRefreshResult(
            summary_text=existing_summary.summary_text if existing_summary else None,
            covered_until_message_id=existing_summary.covered_until_message_id if existing_summary else None,
            summary_generation_ms=0,
            summary_used=existing_summary is not None,
        )

    started_at = time.perf_counter()
    summary_messages = _build_summary_prompt(summary_seed, messages_to_cover)
    summary_text = generate_provider_completion(
        provider_name,
        preferences,
        model_name,
        temperature,
        settings.summary_response_tokens,
        summary_messages,
    ).strip()
    summary_generation_ms = round((time.perf_counter() - started_at) * 1000)

    if not summary_text:
        return SummaryRefreshResult(
            summary_text=existing_summary.summary_text if existing_summary else None,
            covered_until_message_id=existing_summary.covered_until_message_id if existing_summary else None,
            summary_generation_ms=summary_generation_ms,
            summary_used=existing_summary is not None,
        )

    source_token_count = sum(estimate_message_tokens(message['role'], message['content']) for message in messages_eligible)
    covered_until_message_id = messages_eligible[-1]['id']

    if existing_summary is None:
        existing_summary = ConversationSummary(
            conversation_id=conversation_id,
            summary_text=summary_text,
            covered_until_message_id=covered_until_message_id,
            source_message_count=len(messages_eligible),
            source_token_count=source_token_count,
        )
        db.add(existing_summary)
    else:
        existing_summary.summary_text = summary_text
        existing_summary.covered_until_message_id = covered_until_message_id
        existing_summary.source_message_count = len(messages_eligible)
        existing_summary.source_token_count = source_token_count

    db.commit()
    db.refresh(existing_summary)

    return SummaryRefreshResult(
        summary_text=existing_summary.summary_text,
        covered_until_message_id=existing_summary.covered_until_message_id,
        summary_generation_ms=summary_generation_ms,
        summary_used=True,
    )