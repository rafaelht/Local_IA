from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.v1.routes.auth import get_current_user
from app.core.config import settings
from app.db.models import ModelPreference, User, UserPreference
from app.db.session import get_db
from app.schemas.preferences import (
    FavoriteModelCreate,
    FavoriteModelRead,
    UserPreferenceRead,
    UserPreferenceUpdate,
)
from app.services.chat import (
    SUPPORTED_PROVIDERS,
    check_provider_health,
    list_provider_models,
    normalize_provider_url,
)

router = APIRouter()


def get_or_create_user_preferences(db: Session, user_id: int) -> UserPreference:
    preferences = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
    if preferences:
        updated = False
        if not preferences.ollama_api_url:
            preferences.ollama_api_url = settings.ollama_api_url
            updated = True
        if not preferences.litert_api_url:
            preferences.litert_api_url = settings.litert_api_url
            updated = True
        if updated:
            db.commit()
            db.refresh(preferences)
        return preferences

    preferences = UserPreference(
        user_id=user_id,
        ollama_api_url=settings.ollama_api_url,
        litert_api_url=settings.litert_api_url,
    )
    db.add(preferences)
    db.commit()
    db.refresh(preferences)
    return preferences


@router.get('', response_model=UserPreferenceRead)
def read_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserPreference:
    return get_or_create_user_preferences(db, current_user.id)


@router.patch('', response_model=UserPreferenceRead)
def update_preferences(
    preferences_update: UserPreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserPreference:
    preferences = get_or_create_user_preferences(db, current_user.id)
    provided_fields = preferences_update.model_fields_set

    if preferences_update.theme is not None:
        if preferences_update.theme not in {'dark', 'light'}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Tema inválido')
        preferences.theme = preferences_update.theme
    if preferences_update.dev_mode is not None:
        preferences.dev_mode = preferences_update.dev_mode
    if preferences_update.default_provider is not None:
        if preferences_update.default_provider not in SUPPORTED_PROVIDERS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Proveedor inválido')
        provider_changed = preferences.default_provider != preferences_update.default_provider
        preferences.default_provider = preferences_update.default_provider
        if provider_changed and 'default_model' not in provided_fields:
            # Avoid carrying over a model name that belongs to another provider.
            preferences.default_model = None
    if 'default_model' in provided_fields:
        preferences.default_model = preferences_update.default_model or None
    if preferences_update.ollama_api_url is not None:
        try:
            preferences.ollama_api_url = normalize_provider_url(preferences_update.ollama_api_url)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if preferences_update.litert_api_url is not None:
        try:
            preferences.litert_api_url = normalize_provider_url(preferences_update.litert_api_url)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if preferences_update.temperature is not None:
        preferences.temperature = preferences_update.temperature
    if preferences_update.context_length is not None:
        preferences.context_length = preferences_update.context_length

    db.commit()
    db.refresh(preferences)
    return preferences


@router.get('/favorite-models', response_model=list[FavoriteModelRead])
def list_favorite_models(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ModelPreference]:
    return (
        db.query(ModelPreference)
        .filter(
            ModelPreference.user_id == current_user.id,
            ModelPreference.is_favorite.is_(True),
        )
        .order_by(ModelPreference.created_at.desc())
        .all()
    )


@router.get('/providers/{provider}/health')
def provider_health(
    provider: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Proveedor inválido')

    preferences = get_or_create_user_preferences(db, current_user.id)
    return {'healthy': check_provider_health(provider, preferences)}


@router.get('/providers/{provider}/models')
def provider_models(
    provider: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, list[dict]]:
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Proveedor inválido')

    preferences = get_or_create_user_preferences(db, current_user.id)
    try:
        models = list_provider_models(provider, preferences)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return {'data': models}


@router.post('/favorite-models', response_model=FavoriteModelRead, status_code=status.HTTP_201_CREATED)
def add_favorite_model(
    favorite_in: FavoriteModelCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ModelPreference:
    if favorite_in.provider_name not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Proveedor inválido')

    existing = (
        db.query(ModelPreference)
        .filter(
            ModelPreference.user_id == current_user.id,
            ModelPreference.provider_name == favorite_in.provider_name,
            ModelPreference.model_name == favorite_in.model_name,
        )
        .first()
    )

    if existing:
        existing.is_favorite = True
        existing.temperature = favorite_in.temperature
        existing.context_length = favorite_in.context_length
        db.commit()
        db.refresh(existing)
        return existing

    favorite = ModelPreference(
        user_id=current_user.id,
        provider_name=favorite_in.provider_name,
        model_name=favorite_in.model_name,
        temperature=favorite_in.temperature,
        context_length=favorite_in.context_length,
        is_favorite=True,
    )
    db.add(favorite)
    db.commit()
    db.refresh(favorite)
    return favorite


@router.delete('/favorite-models/{favorite_id}', status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite_model(
    favorite_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    favorite = (
        db.query(ModelPreference)
        .filter(
            ModelPreference.id == favorite_id,
            ModelPreference.user_id == current_user.id,
        )
        .first()
    )
    if not favorite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Modelo favorito no encontrado')

    db.delete(favorite)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
