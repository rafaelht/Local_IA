from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.v1.routes.auth import get_current_user
from app.core.jwt import decode_access_token
from app.db.models import Conversation, Message, User
from app.db.session import get_db
from app.schemas.conversation import (
    ConversationCreate,
    ConversationRead,
    ConversationUpdate,
    MessageCreate,
    MessageRead,
)

router = APIRouter()


def get_user_conversation(db: Session, conversation_id: int, user_id: int) -> Conversation:
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Conversación no encontrada')
    return conversation


@router.get('', response_model=list[ConversationRead])
def list_conversations(
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Conversation]:
    query = db.query(Conversation).filter(Conversation.user_id == current_user.id)
    if search:
        query = query.filter(
            Conversation.title.ilike(f"%{search}%") |
            Conversation.messages.any(Message.content.ilike(f"%{search}%"))
        )
    return (
        query.order_by(Conversation.pinned.desc(), Conversation.updated_at.desc())
        .all()
    )


@router.post('', response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
def create_conversation(
    conversation_in: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Conversation:
    title = conversation_in.title or 'Nueva conversación'
    conversation = Conversation(title=title, user_id=current_user.id)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get('/{conversation_id}', response_model=ConversationRead)
def get_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Conversation:
    return get_user_conversation(db, conversation_id, current_user.id)


@router.put('/{conversation_id}', response_model=ConversationRead)
def update_conversation(
    conversation_id: int,
    conversation_update: ConversationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Conversation:
    conversation = get_user_conversation(db, conversation_id, current_user.id)
    if conversation_update.title is not None:
        conversation.title = conversation_update.title
    if conversation_update.pinned is not None:
        conversation.pinned = conversation_update.pinned
    if conversation_update.favorite is not None:
        conversation.favorite = conversation_update.favorite
    conversation.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(conversation)
    return conversation


@router.delete('/{conversation_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    conversation = get_user_conversation(db, conversation_id, current_user.id)
    db.delete(conversation)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post('/{conversation_id}/messages', response_model=MessageRead, status_code=status.HTTP_201_CREATED)
def create_message(
    conversation_id: int,
    message_in: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Message:
    conversation = get_user_conversation(db, conversation_id, current_user.id)
    message = Message(
        conversation_id=conversation.id,
        role=message_in.role,
        content=message_in.content,
    )
    db.add(message)
    conversation.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(message)
    return message


@router.delete('/{conversation_id}/messages/{message_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_message(
    conversation_id: int,
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    conversation = get_user_conversation(db, conversation_id, current_user.id)
    message = (
        db.query(Message)
        .filter(Message.id == message_id, Message.conversation_id == conversation.id)
        .first()
    )
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Mensaje no encontrado')
    db.delete(message)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
