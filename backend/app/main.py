from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.conversations import router as conversations_router
from app.api.v1.routes.preferences import router as preferences_router
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine

app = FastAPI(title='Local LLM Interface API', version='0.1.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:5173'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(auth_router, prefix='/api/v1/auth', tags=['auth'])
app.include_router(conversations_router, prefix='/api/v1/conversations', tags=['conversations'])
app.include_router(preferences_router, prefix='/api/v1/preferences', tags=['preferences'])
app.include_router(health_router, prefix='/api/v1', tags=['health'])


@app.on_event('startup')
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get('/')
def root() -> dict:
    return {'status': 'ok', 'message': 'Local LLM Interface backend is ready.'}
