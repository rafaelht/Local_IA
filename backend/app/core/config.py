import os

from fastapi.security import OAuth2PasswordBearer


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
    image_token_cost: int = int(os.getenv('IMAGE_TOKEN_COST', '256'))
    summary_trigger_messages: int = int(os.getenv('SUMMARY_TRIGGER_MESSAGES', '40'))
    summary_trigger_tokens: int = int(os.getenv('SUMMARY_TRIGGER_TOKENS', '6000'))
    summary_keep_recent_messages: int = int(os.getenv('SUMMARY_KEEP_RECENT_MESSAGES', '8'))
    summary_response_tokens: int = int(os.getenv('SUMMARY_RESPONSE_TOKENS', '256'))
    active_conversation_cache_size: int = int(os.getenv('ACTIVE_CONVERSATION_CACHE_SIZE', '128'))
    model_request_timeout: int = int(os.getenv('MODEL_REQUEST_TIMEOUT', '120'))
    system_prompt: str | None = os.getenv('SYSTEM_PROMPT')

    # CORS: comma-separated list of allowed origins.
    # Example: CORS_ORIGINS=https://chat.midominio.com,http://localhost:5173
    # Leave unset to allow all origins (development only).
    cors_origins: list[str] = _parse_cors_origins(
        os.getenv('CORS_ORIGINS', '')
    )


settings = Settings()
