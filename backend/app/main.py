from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.conversations import router as conversations_router
from app.api.v1.routes.preferences import router as preferences_router
from app.api.v1.routes.users import router as users_router

from app.db.base import Base
from app.db.session import engine
from app.services.litert_conversation_manager import litert_conversation_manager
from sqlalchemy import inspect, text


def ensure_schema_compatibility() -> None:
    inspector = inspect(engine)
    columns = {column['name'] for column in inspector.get_columns('user_preferences')}
    missing_columns = {
        'ollama_api_url': 'ALTER TABLE user_preferences ADD COLUMN ollama_api_url VARCHAR(512)',
        'litert_api_url': 'ALTER TABLE user_preferences ADD COLUMN litert_api_url VARCHAR(512)',
    }

    with engine.begin() as connection:
        for column_name, ddl in missing_columns.items():
            if column_name not in columns:
                connection.execute(text(ddl))


# -----------------------------
# Lifespan (startup / shutdown)
# -----------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(bind=engine)
    ensure_schema_compatibility()

    # Seed initial admin user
    from app.db.seed import create_initial_admin
    create_initial_admin()

    yield

    # Shutdown (si algún día necesitas cerrar cosas)
    litert_conversation_manager.shutdown()


app = FastAPI(
    title="Local LLM Interface API",
    version="0.1.0",
    lifespan=lifespan,
)


# -----------------------------
# CORS
# -----------------------------
# If CORS_ORIGINS env var is set, use explicit list with credentials support.
# Otherwise fall back to allow-all (suitable for local dev only).
_cors_origins = settings.cors_origins
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# -----------------------------
# Routers
# -----------------------------
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users_router, prefix="/api/v1", tags=["users"])
app.include_router(conversations_router, prefix="/api/v1/conversations", tags=["conversations"])
app.include_router(preferences_router, prefix="/api/v1/preferences", tags=["preferences"])
app.include_router(health_router, prefix="/api/v1", tags=["health"])


# -----------------------------
# Root
# -----------------------------
@app.get("/")
def root() -> dict:
    return {
        "status": "ok",
        "message": "Local LLM Interface backend is ready.",
    }