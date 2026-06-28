from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import get_db
from app.db.models import User, UserPreference
from app.schemas.auth import CreateUserRequest, UpdateUserRequest, UserResponse
from app.api.v1.routes.auth import get_current_user

router = APIRouter()


@router.post('/users', response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    user_data: CreateUserRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Create a new user (admin only)."""
    if current_user.role != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Solo administradores pueden crear usuarios')

    # Check if email already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='El email ya está registrado')

    # Check if nickname already exists (if provided)
    if user_data.nickname:
        existing_nickname = db.query(User).filter(User.nickname == user_data.nickname).first()
        if existing_nickname:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='El nickname ya está registrado')

    # Validate role
    if user_data.role not in ['user', 'admin']:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='El rol debe ser "user" o "admin"')

    # Create new user
    new_user = User(
        email=user_data.email,
        nickname=user_data.nickname,
        full_name=user_data.full_name,
        hashed_password=hash_password(user_data.password),
        role=user_data.role,
    )
    db.add(new_user)
    db.flush()

    # Create default preferences for new user
    preferences = UserPreference(user_id=new_user.id)
    db.add(preferences)
    db.commit()
    db.refresh(new_user)

    return new_user


@router.get('/users', response_model=list[UserResponse])
def list_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[User]:
    """List all users (admin only)."""
    if current_user.role != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Solo administradores pueden listar usuarios')

    return db.query(User).all()


@router.put('/users/{user_id}', response_model=UserResponse)
def update_user(
    user_id: int,
    user_data: UpdateUserRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Update a user (admin only)."""
    if current_user.role != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Solo administradores pueden editar usuarios')

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Usuario no encontrado')

    # Update nickname if provided
    if user_data.nickname is not None:
        existing_nickname = db.query(User).filter(User.nickname == user_data.nickname, User.id != user_id).first()
        if existing_nickname:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='El nickname ya está registrado')
        user.nickname = user_data.nickname

    # Update full_name if provided
    if user_data.full_name is not None:
        user.full_name = user_data.full_name

    # Update password if provided
    if user_data.password:
        user.hashed_password = hash_password(user_data.password)

    # Update is_active if provided
    if user_data.is_active is not None:
        user.is_active = user_data.is_active

    # Update role if provided
    if user_data.role is not None:
        if user_data.role not in ['user', 'admin']:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='El rol debe ser "user" o "admin"')
        user.role = user_data.role

    db.commit()
    db.refresh(user)
    return user


@router.delete('/users/{user_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a user (admin only)."""
    if current_user.role != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Solo administradores pueden borrar usuarios')

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Usuario no encontrado')

    # Prevent deleting the current admin
    if user.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='No puedes borrarte a ti mismo')

    db.delete(user)
    db.commit()
