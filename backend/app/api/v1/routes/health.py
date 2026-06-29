from fastapi import APIRouter

from app.services.litert_conversation_manager import litert_conversation_manager

router = APIRouter()


@router.get('/health')
def health() -> dict:
    return {'status': 'ok', 'message': 'backend healthy'}


@router.get('/health/litert-manager')
def litert_manager_health() -> dict:
    return litert_conversation_manager.diagnostics()
