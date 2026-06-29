from __future__ import annotations

import base64
import json
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Generator

from app.core.config import settings
from app.db.models import Message


@dataclass
class _ConversationRuntime:
    conversation: Any
    lock: threading.RLock = field(default_factory=threading.RLock)
    last_access_at: float = field(default_factory=time.monotonic)
    hydrated_until_message_id: int = 0
    model_name: str | None = None


class LiteRTConversationManager:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._engine = None
        self._model_path: str | None = None
        self._runtimes: OrderedDict[int, _ConversationRuntime] = OrderedDict()
        self._stats: dict[str, int] = {
            'engine_reloads': 0,
            'hydrations': 0,
            'reuses': 0,
            'evictions_timeout': 0,
            'evictions_lru': 0,
            'invalidations': 0,
            'sdk_errors': 0,
            'http_fallbacks': 0,
        }

    def _increment_stat_locked(self, key: str, amount: int = 1) -> None:
        self._stats[key] = self._stats.get(key, 0) + amount

    @property
    def enabled(self) -> bool:
        return settings.litert_sdk_enabled

    def _require_sdk_enabled(self) -> None:
        if not settings.litert_sdk_enabled:
            raise RuntimeError('LiteRT SDK path is disabled')

    def _resolve_model_path(self) -> str:
        model_path = settings.litert_sdk_model_path.strip()
        if not model_path:
            raise RuntimeError('LITERT_SDK_MODEL_PATH is required when LITERT_SDK_ENABLED=true')
        return model_path

    def _get_engine_locked(self, model_name: str | None = None):
        self._require_sdk_enabled()
        model_path = model_name or self._resolve_model_path()

        if self._engine is not None and self._model_path == model_path:
            return self._engine

        import litert_lm  # Lazy import to avoid hard dependency when SDK mode is disabled.

        if self._engine is not None:
            self._close_all_runtimes_locked()
            self._engine.close()
            self._engine = None

        backend = litert_lm.Backend.CPU()
        self._engine = litert_lm.Engine(
            model_path=model_path,
            backend=backend,
            max_num_tokens=settings.litert_sdk_engine_max_tokens,
            cache_dir=settings.litert_sdk_cache_dir,
        )
        self._model_path = model_path
        self._increment_stat_locked('engine_reloads')
        return self._engine

    def _close_all_runtimes_locked(self) -> None:
        for runtime in self._runtimes.values():
            try:
                runtime.conversation.close()
            except Exception:
                pass
        self._runtimes.clear()

    def shutdown(self) -> None:
        with self._lock:
            self._close_all_runtimes_locked()
            if self._engine is not None:
                try:
                    self._engine.close()
                except Exception:
                    pass
                self._engine = None
                self._model_path = None

    def _touch_runtime_locked(self, conversation_id: int) -> None:
        runtime = self._runtimes.get(conversation_id)
        if runtime is None:
            return
        runtime.last_access_at = time.monotonic()
        self._runtimes.move_to_end(conversation_id)

    def _evict_inactive_locked(self) -> None:
        now = time.monotonic()
        timeout_seconds = max(0, settings.litert_sdk_conversation_timeout_seconds)
        max_active = max(1, settings.litert_sdk_max_active_conversations)

        expired_ids: list[int] = []
        if timeout_seconds > 0:
            for conversation_id, runtime in self._runtimes.items():
                if now - runtime.last_access_at > timeout_seconds:
                    expired_ids.append(conversation_id)

        for conversation_id in expired_ids:
            runtime = self._runtimes.pop(conversation_id, None)
            if runtime is None:
                continue
            try:
                runtime.conversation.close()
            except Exception:
                pass
            self._increment_stat_locked('evictions_timeout')

        while len(self._runtimes) > max_active:
            _, runtime = self._runtimes.popitem(last=False)
            try:
                runtime.conversation.close()
            except Exception:
                pass
            self._increment_stat_locked('evictions_lru')

    def invalidate(self, conversation_id: int) -> None:
        with self._lock:
            runtime = self._runtimes.pop(conversation_id, None)
            if runtime is None:
                return
            try:
                runtime.conversation.close()
            except Exception:
                pass
            self._increment_stat_locked('invalidations')

    def mark_http_fallback(self) -> None:
        with self._lock:
            self._increment_stat_locked('http_fallbacks')

    def diagnostics(self) -> dict[str, Any]:
        with self._lock:
            now = time.monotonic()
            runtimes = [
                {
                    'conversation_id': conversation_id,
                    'idle_seconds': round(max(0.0, now - runtime.last_access_at), 2),
                    'hydrated_until_message_id': runtime.hydrated_until_message_id,
                    'model_name': runtime.model_name,
                }
                for conversation_id, runtime in self._runtimes.items()
            ]
            return {
                'enabled': settings.litert_sdk_enabled,
                'model_path': self._model_path or settings.litert_sdk_model_path,
                'engine_loaded': self._engine is not None,
                'active_conversations': len(self._runtimes),
                'max_active_conversations': settings.litert_sdk_max_active_conversations,
                'conversation_timeout_seconds': settings.litert_sdk_conversation_timeout_seconds,
                'stats': dict(self._stats),
                'runtimes': runtimes,
            }

    def _decode_db_content(self, raw_content: str) -> Any:
        try:
            if raw_content.startswith('['):
                parsed = json.loads(raw_content)
                if isinstance(parsed, list):
                    return parsed
        except (json.JSONDecodeError, AttributeError):
            pass
        return raw_content

    def _to_litert_content(self, content: Any) -> list[dict[str, Any]]:
        if isinstance(content, str):
            return [{'type': 'text', 'text': content}]

        if not isinstance(content, list):
            return [{'type': 'text', 'text': str(content)}]

        normalized: list[dict[str, Any]] = []
        for item in content:
            if not isinstance(item, dict):
                normalized.append({'type': 'text', 'text': str(item)})
                continue

            item_type = item.get('type')
            if item_type == 'text':
                normalized.append({'type': 'text', 'text': str(item.get('text', ''))})
                continue

            if item_type == 'image_url':
                image_url = item.get('image_url')
                if isinstance(image_url, dict):
                    url = image_url.get('url')
                else:
                    url = None
                if isinstance(url, str) and url.startswith('data:image/') and ',' in url:
                    _prefix, b64data = url.split(',', 1)
                    try:
                        base64.b64decode(b64data, validate=False)
                        normalized.append({'type': 'image', 'blob': b64data})
                        continue
                    except Exception:
                        pass
                normalized.append({'type': 'text', 'text': '[imagen adjunta]'})
                continue

            normalized.append({'type': 'text', 'text': str(item)})

        return normalized or [{'type': 'text', 'text': ''}]

    def _normalize_role(self, role: str) -> str:
        lower = role.lower()
        if lower == 'assistant':
            return 'model'
        if lower in {'model', 'user', 'system', 'tool'}:
            return lower
        return 'user'

    def _history_to_litert_messages(
        self,
        db_messages: list[Message | dict[str, Any]],
        exclude_message_id: int | None,
    ) -> tuple[list[dict[str, Any]], int]:
        max_message_id = 0
        messages: list[dict[str, Any]] = []

        for message in db_messages:
            if isinstance(message, dict):
                message_id = int(message.get('id', 0) or 0)
                role = self._normalize_role(str(message.get('role', 'user')))
                content = message.get('content')
                if isinstance(content, str):
                    content = self._decode_db_content(content)
            else:
                message_id = int(message.id)
                role = self._normalize_role(message.role)
                content = self._decode_db_content(message.content)

            if exclude_message_id is not None and message_id == exclude_message_id:
                continue

            max_message_id = max(max_message_id, message_id)
            messages.append(
                {
                    'role': role,
                    'content': self._to_litert_content(content),
                }
            )

        return messages, max_message_id

    def _extract_chunk_text(self, chunk: Any) -> str:
        if not isinstance(chunk, dict):
            return ''

        content = chunk.get('content')
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get('type') == 'text':
                    text = item.get('text')
                    if isinstance(text, str):
                        parts.append(text)
            return ''.join(parts)

        return ''

    def list_models(self) -> list[dict[str, Any]]:
        if not settings.litert_sdk_enabled:
            return []

        model_path = self._resolve_model_path()
        model_name = model_path.split('/')[-1].split('\\')[-1]
        return [{'id': model_path, 'name': model_name}]

    def check_health(self) -> bool:
        if not settings.litert_sdk_enabled:
            return False
        try:
            with self._lock:
                self._get_engine_locked()
                self._evict_inactive_locked()
            return True
        except Exception:
            return False

    def stream_message(
        self,
        conversation_id: int,
        user_message_content: str | list[dict[str, Any]],
        history_messages: list[Message | dict[str, Any]],
        current_user_message_id: int,
        model_name: str | None,
        system_prompt: str | None,
        temperature: float | None,
    ) -> tuple[Generator[str, None, None], dict[str, Any]]:
        hydration_started_at = time.perf_counter()
        hydration_ms = 0

        with self._lock:
            runtime = self._runtimes.get(conversation_id)
            reused_runtime = runtime is not None

            if runtime is None or (model_name and runtime.model_name and runtime.model_name != model_name):
                engine = self._get_engine_locked(model_name=model_name)
                hydrated_messages, hydrated_until = self._history_to_litert_messages(
                    history_messages,
                    exclude_message_id=current_user_message_id,
                )

                import litert_lm  # Lazy import by design.

                sampler_config = litert_lm.SamplerConfig(temperature=temperature)
                conversation = engine.create_conversation(
                    messages=hydrated_messages,
                    system_message=system_prompt,
                    sampler_config=sampler_config,
                )

                runtime = _ConversationRuntime(
                    conversation=conversation,
                    hydrated_until_message_id=hydrated_until,
                    model_name=model_name,
                )
                hydration_ms = round((time.perf_counter() - hydration_started_at) * 1000)
                self._increment_stat_locked('hydrations')
                self._runtimes[conversation_id] = runtime
                self._touch_runtime_locked(conversation_id)
                self._evict_inactive_locked()
            else:
                self._increment_stat_locked('reuses')
                self._touch_runtime_locked(conversation_id)

        prepared_content = self._to_litert_content(user_message_content)

        def _iterator() -> Generator[str, None, None]:
            with runtime.lock:
                try:
                    for chunk in runtime.conversation.send_message_async(
                        {'role': 'user', 'content': prepared_content}
                    ):
                        text = self._extract_chunk_text(chunk)
                        if text:
                            yield text

                    runtime.hydrated_until_message_id = max(
                        runtime.hydrated_until_message_id,
                        int(current_user_message_id),
                    )
                    runtime.last_access_at = time.monotonic()
                except Exception as exc:
                    with self._lock:
                        self._increment_stat_locked('sdk_errors')
                        self.invalidate(conversation_id)
                    raise RuntimeError(f'LiteRT SDK stream failed: {exc}') from exc

            with self._lock:
                self._touch_runtime_locked(conversation_id)
                self._evict_inactive_locked()

        metadata = {
            'reused_runtime': reused_runtime,
            'history_message_count': len(history_messages),
            'hydration_ms': hydration_ms,
            'active_conversations': len(self._runtimes),
        }
        return _iterator(), metadata


litert_conversation_manager = LiteRTConversationManager()
