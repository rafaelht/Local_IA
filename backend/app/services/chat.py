import codecs
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Generator

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Message


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


def get_provider_url(provider: str) -> str:
    if provider == 'ollama':
        return urllib.parse.urljoin(settings.ollama_api_url, '/v1/chat/completions')
    return urllib.parse.urljoin(settings.litert_api_url, '/v1/chat/completions')


def build_model_payload(
    provider: str,
    model: str | None,
    temperature: float | None,
    max_tokens: int | None,
    messages: list[dict],
) -> dict:
    payload = {
        'model': model or 'default',
        'messages': messages,
        'temperature': temperature if temperature is not None else 0.7,
        'stream': True,
    }
    if max_tokens is not None:
        payload['max_tokens'] = max_tokens
    return payload


def _parse_sse_lines(buffer: str, assistant_parts: list[str]) -> str:
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
    return buffer


def stream_provider_response(provider_url: str, payload: dict, assistant_parts: list[str]) -> Generator[bytes, None, None]:
    body = json.dumps(payload).encode('utf-8')
    request = urllib.request.Request(
        provider_url,
        data=body,
        headers={
            'Content-Type': 'application/json',
        },
        method='POST',
    )

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
                buffer = _parse_sse_lines(buffer, assistant_parts)
                yield chunk

            trailing = decoder.decode(b'', final=True)
            if trailing:
                buffer += trailing
                buffer = _parse_sse_lines(buffer, assistant_parts)

            if buffer:
                yield buffer.encode('utf-8')
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'Provider HTTP error: {exc.code} {exc.reason}') from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f'Provider connection error: {exc.reason}') from exc


def save_assistant_message(db: Session, conversation_id: int, content: str) -> Message:
    assistant_message = Message(conversation_id=conversation_id, role='assistant', content=content)
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)
    return assistant_message
