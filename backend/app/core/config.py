import os

from fastapi.security import OAuth2PasswordBearer

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
    model_request_timeout: int = int(os.getenv('MODEL_REQUEST_TIMEOUT', '120'))
    system_prompt: str | None = os.getenv('SYSTEM_PROMPT')


settings = Settings()
