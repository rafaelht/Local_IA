import codecs
import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Generator

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Message
from app.services.litert_conversation_manager import litert_conversation_manager


SUPPORTED_PROVIDERS = {'liteRT', 'ollama'}
INVALID_MODEL_SENTINELS = {'default'}


def normalize_provider_url(raw_url: str) -> str:
    value = raw_url.strip()
    if not value:
        raise ValueError('Provider URL cannot be empty')
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise ValueError('Provider URL must be a valid http(s) URL')
    return value.rstrip('/')


def get_recent_messages(db: Session, conversation_id: int, max_messages: int) -> list[Message]:
    return (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(max_messages)
        .all()[::-1]
    )


def build_chat_history(messages: list[Message], system_prompt: str | None = None) -> list[dict]:
    """Build chat history, preserving complex content (text + images)."""
    history = []
    if system_prompt:
        history.append({'role': 'system', 'content': system_prompt})

    for message in messages:
        # Try to parse content as JSON (for vision messages with images)
        content = message.content
        try:
            # If content is JSON-serialized list, parse it
            if content.startswith('['):
                parsed = json.loads(content)
                if isinstance(parsed, list):
                    content = parsed
        except (json.JSONDecodeError, AttributeError):
            # If not JSON or not a list, keep as string
            pass
        
        history.append({'role': message.role, 'content': content})

    return history


def get_provider_base_url(provider: str, preferences: object | None = None) -> str:
    if provider == 'ollama':
        candidate = getattr(preferences, 'ollama_api_url', None) or settings.ollama_api_url
    else:
        candidate = getattr(preferences, 'litert_api_url', None) or settings.litert_api_url
    return normalize_provider_url(candidate)


def get_provider_url(provider: str, preferences: object | None = None) -> str:
    return urllib.parse.urljoin(get_provider_base_url(provider, preferences), '/v1/chat/completions')


def get_provider_native_url(provider: str, preferences: object | None = None) -> str:
    base_url = get_provider_base_url(provider, preferences)
    if provider == 'ollama':
        return urllib.parse.urljoin(base_url, '/api/chat')
    return urllib.parse.urljoin(base_url, '/v1/chat/completions')


def _read_json_response(request: urllib.request.Request, timeout: int = 10) -> dict:
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode('utf-8'))


def list_provider_models(provider: str, preferences: object | None = None, use_sdk: bool = True) -> list[dict]:
    if provider == 'liteRT' and settings.litert_sdk_enabled and use_sdk:
        return litert_conversation_manager.list_models()

    base_url = get_provider_base_url(provider, preferences)
    models_url = urllib.parse.urljoin(base_url, '/v1/models')
    request = urllib.request.Request(models_url, method='GET')

    try:
        payload = _read_json_response(request)
    except urllib.error.HTTPError as exc:
        if provider == 'ollama' and exc.code == 404:
            native_models_url = urllib.parse.urljoin(base_url, '/api/tags')
            native_request = urllib.request.Request(native_models_url, method='GET')
            try:
                payload = _read_json_response(native_request)
            except urllib.error.HTTPError as native_exc:
                raise RuntimeError(f'Provider HTTP error: {native_exc.code} {native_exc.reason}') from native_exc
            except urllib.error.URLError as native_exc:
                raise RuntimeError(f'Provider connection error: {native_exc.reason}') from native_exc

            models = payload.get('models', []) if isinstance(payload, dict) else []
            if not isinstance(models, list):
                return []
            return [
                {
                    'id': model.get('model') or model.get('name'),
                    'name': model.get('name') or model.get('model'),
                }
                for model in models
                if isinstance(model, dict) and (model.get('model') or model.get('name'))
            ]
        raise RuntimeError(f'Provider HTTP error: {exc.code} {exc.reason}') from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f'Provider connection error: {exc.reason}') from exc

    models = payload.get('data', []) if isinstance(payload, dict) else []
    if not isinstance(models, list):
        return []
    return [model for model in models if isinstance(model, dict)]


def check_provider_health(provider: str, preferences: object | None = None, use_sdk: bool = True) -> bool:
    if provider == 'liteRT' and settings.litert_sdk_enabled and use_sdk:
        return litert_conversation_manager.check_health()

    try:
        list_provider_models(provider, preferences, use_sdk=use_sdk)
        return True
    except RuntimeError:
        return False


def normalize_model_name(model: str | None) -> str | None:
    if model is None:
        return None
    normalized = model.strip()
    if not normalized:
        return None
    if normalized.lower() in INVALID_MODEL_SENTINELS:
        return None
    return normalized


def resolve_provider_model(
    provider: str,
    model: str | None,
    preferences: object | None = None,
    use_sdk: bool = True,
) -> str:
    if provider == 'liteRT' and settings.litert_sdk_enabled and use_sdk:
        sdk_model_path = settings.litert_sdk_model_path.strip()
        if not sdk_model_path:
            raise RuntimeError('LITERT_SDK_MODEL_PATH is required when LITERT_SDK_ENABLED=true')
        return sdk_model_path

    normalized_model = normalize_model_name(model)
    if normalized_model is not None:
        return normalized_model

    models = list_provider_models(provider, preferences, use_sdk=use_sdk)
    for model_info in models:
        if not isinstance(model_info, dict):
            continue
        candidate = model_info.get('id') or model_info.get('name')
        if isinstance(candidate, str):
            normalized_candidate = normalize_model_name(candidate)
            if normalized_candidate is not None:
                return normalized_candidate

    raise RuntimeError('No available model found for provider')


def build_model_payload(
    provider: str,
    model: str,
    temperature: float | None,
    max_tokens: int | None,
    messages: list[dict],
    mode: str = 'openai',
) -> dict:
    resolved_temperature = temperature if temperature is not None else 0.7
    resolved_model = model

    if mode == 'ollama-native':
        payload = {
            'model': resolved_model,
            'messages': messages,
            'stream': True,
            'options': {
                'temperature': resolved_temperature,
            },
        }
        if max_tokens is not None:
            payload['options']['num_predict'] = max_tokens
        return payload

    payload = {
        'model': resolved_model,
        'messages': messages,
        'temperature': resolved_temperature,
        'stream': True,
    }
    if max_tokens is not None:
        payload['max_tokens'] = max_tokens
    return payload


def generate_provider_completion(
    provider: str,
    preferences: object | None,
    model: str | None,
    temperature: float | None,
    max_tokens: int | None,
    messages: list[dict],
) -> str:
    resolved_model = resolve_provider_model(provider, model, preferences)
    provider_url = get_provider_url(provider, preferences)
    payload = build_model_payload(provider, resolved_model, temperature, max_tokens, messages)
    payload['stream'] = False
    body = json.dumps(payload).encode('utf-8')
    request = urllib.request.Request(
        provider_url,
        data=body,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )

    try:
        with urllib.request.urlopen(request, timeout=settings.model_request_timeout) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data.get('choices', [{}])[0].get('message', {}).get('content', '')
    except urllib.error.HTTPError as exc:
        if provider == 'ollama' and exc.code == 404:
            native_provider_url = get_provider_native_url(provider, preferences)
            native_payload = build_model_payload(
                provider,
                resolved_model,
                temperature,
                max_tokens,
                messages,
                mode='ollama-native',
            )
            native_payload['stream'] = False
            native_body = json.dumps(native_payload).encode('utf-8')
            native_request = urllib.request.Request(
                native_provider_url,
                data=native_body,
                headers={'Content-Type': 'application/json'},
                method='POST',
            )
            with urllib.request.urlopen(native_request, timeout=settings.model_request_timeout) as response:
                data = json.loads(response.read().decode('utf-8'))
                return data.get('message', {}).get('content', '')
        raise RuntimeError(f'Provider HTTP error: {exc.code} {exc.reason}') from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f'Provider connection error: {exc.reason}') from exc


def _parse_sse_lines(buffer: str, assistant_parts: list[str]) -> tuple[str, bool]:
    emitted_content = False
    lines = buffer.split('\n')
    buffer = lines.pop() if lines else ''

    for line in lines:
        clean_line = line.strip()
        if not clean_line:
            continue
        if clean_line == 'data: [DONE]':
            continue
        if clean_line.startswith('data: '):
            data_text = clean_line[6:].strip()
            if not data_text:
                continue
            try:
                data = json.loads(data_text)
            except json.JSONDecodeError:
                continue

            choices = data.get('choices', [])
            if not choices:
                continue

            delta = choices[0].get('delta', {})
            if isinstance(delta, dict):
                content = delta.get('content')
                if isinstance(content, str) and content:
                    assistant_parts.append(content)
                    emitted_content = True
    return buffer, emitted_content


def _parse_ollama_lines(buffer: str, assistant_parts: list[str]) -> tuple[str, list[bytes], bool]:
    events: list[bytes] = []
    emitted_content = False
    lines = buffer.split('\n')
    buffer = lines.pop() if lines else ''

    for line in lines:
        clean_line = line.strip()
        if not clean_line:
            continue

        try:
            data = json.loads(clean_line)
        except json.JSONDecodeError:
            continue

        if not isinstance(data, dict):
            continue

        message = data.get('message', {})
        content = message.get('content') if isinstance(message, dict) else None
        if isinstance(content, str) and content:
            assistant_parts.append(content)
            emitted_content = True
            chunk_payload = {
                'choices': [
                    {
                        'delta': {
                            'content': content,
                        }
                    }
                ]
            }
            events.append(f"data: {json.dumps(chunk_payload, ensure_ascii=False)}\n\n".encode('utf-8'))

        if data.get('done') is True:
            events.append(b'data: [DONE]\n\n')

    return buffer, events, emitted_content


def stream_provider_response(
    provider: str,
    preferences: object | None,
    payload: dict,
    assistant_parts: list[str],
    on_first_token: Callable[[], None] | None = None,
) -> Generator[bytes, None, None]:
    provider_url = get_provider_url(provider, preferences)
    body = json.dumps(payload).encode('utf-8')
    request = urllib.request.Request(
        provider_url,
        data=body,
        headers={
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    first_token_emitted = False

    try:
        with urllib.request.urlopen(request, timeout=settings.model_request_timeout) as response:
            if response.status != 200:
                raise urllib.error.HTTPError(
                    provider_url,
                    response.status,
                    response.reason or 'Model provider error',
                    response.headers,
                    None,
                )

            decoder = codecs.getincrementaldecoder('utf-8')()
            buffer = ''

            while True:
                chunk = response.read(1024)
                if not chunk:
                    break

                text = decoder.decode(chunk)
                buffer += text
                buffer, emitted_content = _parse_sse_lines(buffer, assistant_parts)
                if emitted_content and not first_token_emitted:
                    first_token_emitted = True
                    if on_first_token is not None:
                        on_first_token()
                yield chunk

            trailing = decoder.decode(b'', final=True)
            if trailing:
                buffer += trailing
                buffer, emitted_content = _parse_sse_lines(buffer, assistant_parts)
                if emitted_content and not first_token_emitted:
                    first_token_emitted = True
                    if on_first_token is not None:
                        on_first_token()

            if buffer:
                yield buffer.encode('utf-8')
    except urllib.error.HTTPError as exc:
        if provider == 'ollama' and exc.code == 404:
            native_provider_url = get_provider_native_url(provider, preferences)
            native_payload = build_model_payload(
                provider,
                payload.get('model'),
                payload.get('temperature'),
                payload.get('max_tokens'),
                payload.get('messages', []),
                mode='ollama-native',
            )
            native_body = json.dumps(native_payload).encode('utf-8')
            native_request = urllib.request.Request(
                native_provider_url,
                data=native_body,
                headers={
                    'Content-Type': 'application/json',
                },
                method='POST',
            )

            try:
                with urllib.request.urlopen(native_request, timeout=settings.model_request_timeout) as response:
                    decoder = codecs.getincrementaldecoder('utf-8')()
                    buffer = ''

                    while True:
                        chunk = response.read(1024)
                        if not chunk:
                            break

                        text = decoder.decode(chunk)
                        buffer += text
                        buffer, events, emitted_content = _parse_ollama_lines(buffer, assistant_parts)
                        if emitted_content and not first_token_emitted:
                            first_token_emitted = True
                            if on_first_token is not None:
                                on_first_token()
                        for event in events:
                            yield event

                    trailing = decoder.decode(b'', final=True)
                    if trailing:
                        buffer += trailing
                        buffer, events, emitted_content = _parse_ollama_lines(buffer, assistant_parts)
                        if emitted_content and not first_token_emitted:
                            first_token_emitted = True
                            if on_first_token is not None:
                                on_first_token()
                        for event in events:
                            yield event

                    if assistant_parts and (not events or events[-1] != b'data: [DONE]\n\n'):
                        yield b'data: [DONE]\n\n'
                return
            except urllib.error.HTTPError as native_exc:
                raise RuntimeError(f'Provider HTTP error: {native_exc.code} {native_exc.reason}') from native_exc
            except urllib.error.URLError as native_exc:
                raise RuntimeError(f'Provider connection error: {native_exc.reason}') from native_exc
        raise RuntimeError(f'Provider HTTP error: {exc.code} {exc.reason}') from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f'Provider connection error: {exc.reason}') from exc


def save_assistant_message(db: Session, conversation_id: int, content: str) -> Message:
    assistant_message = Message(conversation_id=conversation_id, role='assistant', content=content)
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)
    return assistant_message
