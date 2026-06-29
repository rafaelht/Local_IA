from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from threading import RLock
from typing import Any

from app.core.config import settings
from app.db.models import Message
from app.services.conversation_context import decode_message_content, estimate_message_tokens


@dataclass
class CachedConversationState:
    conversation_id: int
    messages: list[dict[str, Any]] = field(default_factory=list)
    summary_text: str | None = None
    summary_covered_until_message_id: int | None = None


class ActiveConversationCache:
    def __init__(self, max_size: int):
        self.max_size = max_size
        self._lock = RLock()
        self._entries: OrderedDict[int, CachedConversationState] = OrderedDict()

    def get(self, conversation_id: int) -> CachedConversationState | None:
        with self._lock:
            entry = self._entries.get(conversation_id)
            if entry is None:
                return None
            self._entries.move_to_end(conversation_id)
            return CachedConversationState(
                conversation_id=entry.conversation_id,
                messages=[self._normalize_cached_message(message) for message in entry.messages],
                summary_text=entry.summary_text,
                summary_covered_until_message_id=entry.summary_covered_until_message_id,
            )

    def _normalize_cached_message(self, message: Message | dict[str, Any]) -> dict[str, Any]:
        if isinstance(message, dict):
            normalized = dict(message)
            content = normalized.get('content')
            if isinstance(content, str):
                content = decode_message_content(content)
            normalized['content'] = content
            normalized['tokens'] = int(
                normalized.get('tokens')
                or estimate_message_tokens(str(normalized.get('role', 'user')), content)
            )
            return normalized

        content = decode_message_content(message.content)
        return {
            'id': message.id,
            'role': message.role,
            'content': content,
            'tokens': estimate_message_tokens(message.role, content),
        }

    def set(
        self,
        conversation_id: int,
        messages: list[Message | dict[str, Any]],
        summary_text: str | None = None,
        summary_covered_until_message_id: int | None = None,
    ) -> None:
        with self._lock:
            self._entries[conversation_id] = CachedConversationState(
                conversation_id=conversation_id,
                messages=[self._normalize_cached_message(message) for message in messages],
                summary_text=summary_text,
                summary_covered_until_message_id=summary_covered_until_message_id,
            )
            self._entries.move_to_end(conversation_id)
            while len(self._entries) > self.max_size:
                self._entries.popitem(last=False)

    def update_message(self, conversation_id: int, message_id: int, role: str, raw_content: str) -> None:
        with self._lock:
            entry = self._entries.get(conversation_id)
            if entry is None:
                return
            content = decode_message_content(raw_content)
            token_count = estimate_message_tokens(role, content)
            entry.messages.append({
                'id': message_id,
                'role': role,
                'content': content,
                'tokens': token_count,
            })
            self._entries.move_to_end(conversation_id)

    def update_summary(self, conversation_id: int, summary_text: str | None, covered_until_message_id: int | None) -> None:
        with self._lock:
            entry = self._entries.get(conversation_id)
            if entry is None:
                return
            entry.summary_text = summary_text
            entry.summary_covered_until_message_id = covered_until_message_id
            self._entries.move_to_end(conversation_id)

    def remove_message(self, conversation_id: int, message_id: int) -> None:
        with self._lock:
            entry = self._entries.get(conversation_id)
            if entry is None:
                return
            entry.messages = [message for message in entry.messages if int(message.get('id', 0)) != message_id]
            if entry.summary_covered_until_message_id is not None and message_id <= entry.summary_covered_until_message_id:
                entry.summary_text = None
                entry.summary_covered_until_message_id = None

    def invalidate(self, conversation_id: int) -> None:
        with self._lock:
            self._entries.pop(conversation_id, None)


active_conversation_cache = ActiveConversationCache(settings.active_conversation_cache_size)