import os

from fastapi.security import OAuth2PasswordBearer


def _parse_bool(raw: str, default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {'1', 'true', 'yes', 'on'}


def _parse_cors_origins(raw: str) -> list[str]:
    """Parse comma-separated CORS origins from env var."""
    return [o.strip().rstrip('/') for o in raw.split(',') if o.strip()]


class Settings:
    secret_key: str = os.getenv('SECRET_KEY', 'replace-this-secret')
    algorithm: str = 'HS256'
    access_token_expire_minutes: int = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', '60'))
    database_url: str = os.getenv('DATABASE_URL', 'sqlite:///./app.db')
    initial_admin_email: str = os.getenv('INITIAL_ADMIN_EMAIL', 'admin@local')
    initial_admin_password: str = os.getenv('INITIAL_ADMIN_PASSWORD', 'admin123')
    oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/api/v1/auth/login')
    ollama_api_url: str = os.getenv('OLLAMA_API_URL', 'http://ollama:11434')
    litert_api_url: str = os.getenv('LITERT_API_URL', 'http://10.0.0.84:9379')
    max_context_messages: int = int(os.getenv('MAX_CONTEXT_MESSAGES', '20'))
    model_context_limit: int = int(os.getenv('MODEL_CONTEXT_LIMIT', '8192'))
    context_token_budget: int = int(os.getenv('CONTEXT_TOKEN_BUDGET', '0'))
    response_token_reserve: int = int(os.getenv('RESPONSE_TOKEN_RESERVE', '1024'))
    minimum_context_budget: int = int(os.getenv('MINIMUM_CONTEXT_BUDGET', '256'))
    enable_dynamic_history_budget: bool = _parse_bool(os.getenv('ENABLE_DYNAMIC_HISTORY_BUDGET'), True)
    history_max_prompt_tokens: int = int(os.getenv('HISTORY_MAX_PROMPT_TOKENS', '2048'))
    history_recent_messages_cap: int = int(os.getenv('HISTORY_RECENT_MESSAGES_CAP', '20'))
    history_recent_tokens_cap: int = int(os.getenv('HISTORY_RECENT_TOKENS_CAP', '1800'))
    history_message_char_cap: int = int(os.getenv('HISTORY_MESSAGE_CHAR_CAP', '700'))
    history_response_token_cap: int = int(os.getenv('HISTORY_RESPONSE_TOKEN_CAP', '512'))
    history_include_assistant_messages: bool = _parse_bool(os.getenv('HISTORY_INCLUDE_ASSISTANT_MESSAGES'), True)
    enable_conversation_summary: bool = _parse_bool(os.getenv('ENABLE_CONVERSATION_SUMMARY'), True)
    summary_in_request_path: bool = _parse_bool(os.getenv('SUMMARY_IN_REQUEST_PATH'), False)
    image_token_cost: int = int(os.getenv('IMAGE_TOKEN_COST', '256'))
    summary_trigger_messages: int = int(os.getenv('SUMMARY_TRIGGER_MESSAGES', '20'))
    summary_trigger_tokens: int = int(os.getenv('SUMMARY_TRIGGER_TOKENS', '2800'))
    summary_keep_recent_messages: int = int(os.getenv('SUMMARY_KEEP_RECENT_MESSAGES', '20'))
    summary_response_tokens: int = int(os.getenv('SUMMARY_RESPONSE_TOKENS', '160'))
    active_conversation_cache_size: int = int(os.getenv('ACTIVE_CONVERSATION_CACHE_SIZE', '128'))
    model_request_timeout: int = int(os.getenv('MODEL_REQUEST_TIMEOUT', '120'))
    system_prompt: str | None = os.getenv('SYSTEM_PROMPT')

    # LiteRT-LM SDK integration (stateful conversations + KV cache reuse)
    litert_sdk_enabled: bool = _parse_bool(os.getenv('LITERT_SDK_ENABLED'), False)
    litert_sdk_model_path: str = os.getenv('LITERT_SDK_MODEL_PATH', '')
    litert_sdk_cache_dir: str = os.getenv('LITERT_SDK_CACHE_DIR', '')
    litert_sdk_engine_max_tokens: int | None = (
        int(os.getenv('LITERT_SDK_ENGINE_MAX_TOKENS'))
        if os.getenv('LITERT_SDK_ENGINE_MAX_TOKENS')
        else None
    )
    litert_sdk_fallback_to_http: bool = _parse_bool(os.getenv('LITERT_SDK_FALLBACK_TO_HTTP'), True)
    litert_sdk_max_active_conversations: int = int(os.getenv('LITERT_SDK_MAX_ACTIVE_CONVERSATIONS', '64'))
    litert_sdk_conversation_timeout_seconds: int = int(os.getenv('LITERT_SDK_CONVERSATION_TIMEOUT_SECONDS', '1800'))

    # CORS: comma-separated list of allowed origins.
    # Example: CORS_ORIGINS=https://chat.midominio.com,http://localhost:5173
    # Leave unset to allow all origins (development only).
    cors_origins: list[str] = _parse_cors_origins(
        os.getenv('CORS_ORIGINS', '')
    )


settings = Settings()
