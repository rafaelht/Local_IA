from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.jwt import create_access_token, decode_access_token
from app.core.security import verify_password, hash_password
from app.db.session import get_db
from app.schemas.auth import LoginRequest
from app.schemas.token import Token
from app.schemas.user import UserRead
from app.db.models import User

router = APIRouter()


from typing import Optional


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


def get_current_user(token: str = Depends(settings.oauth2_scheme), db: Session = Depends(get_db)) -> User:
    payload = decode_access_token(token)
    if not payload or 'sub' not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Token inválido')

    email = payload['sub']
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Usuario no encontrado')
    return user


@router.post('/login', response_model=Token)
def login(form_data: LoginRequest, db: Session = Depends(get_db)) -> Token:
    user = authenticate_user(db, form_data.email, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Credenciales inválidas')

    access_token = create_access_token(
        data={'sub': user.email}, expires_delta=timedelta(minutes=settings.access_token_expire_minutes)
    )
    return {'access_token': access_token, 'token_type': 'bearer'}


@router.get('/me', response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> UserRead:
    return current_user
