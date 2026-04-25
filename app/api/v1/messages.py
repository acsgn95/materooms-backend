import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.message import Conversation, Message
from app.schemas.message import MessageCreate, MessageOut, ConversationOut
from app.schemas.common import ok, ResponseEnvelope

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("/conversations", response_model=ResponseEnvelope[list[ConversationOut]])
async def list_conversations(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Conversation).where(
            or_(Conversation.participant_a == current_user.id, Conversation.participant_b == current_user.id)
        ).order_by(Conversation.created_at.desc())
    )
    conversations = result.scalars().all()
    return ok(conversations)


@router.post("/conversations", response_model=ResponseEnvelope[ConversationOut])
async def start_conversation(
    other_user_id: uuid.UUID,
    listing_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if other_user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Kendinizle konuşma başlatamazsınız")

    result = await db.execute(
        select(Conversation).where(
            or_(
                (Conversation.participant_a == current_user.id) & (Conversation.participant_b == other_user_id),
                (Conversation.participant_a == other_user_id) & (Conversation.participant_b == current_user.id),
            )
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return ok(existing)

    conv = Conversation(participant_a=current_user.id, participant_b=other_user_id, listing_id=listing_id)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return ok(conv)


@router.get("/conversations/{conversation_id}/messages", response_model=ResponseEnvelope[list[MessageOut]])
async def get_messages(
    conversation_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = result.scalar_one_or_none()
    if not conv or (conv.participant_a != current_user.id and conv.participant_b != current_user.id):
        raise HTTPException(status_code=404, detail="Konuşma bulunamadı")

    msgs_result = await db.execute(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return ok(msgs_result.scalars().all())


@router.post("/conversations/{conversation_id}/messages", response_model=ResponseEnvelope[MessageOut])
async def send_message(
    conversation_id: uuid.UUID,
    body: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = result.scalar_one_or_none()
    if not conv or (conv.participant_a != current_user.id and conv.participant_b != current_user.id):
        raise HTTPException(status_code=404, detail="Konuşma bulunamadı")

    msg = Message(conversation_id=conversation_id, sender_id=current_user.id, content=body.content)
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return ok(msg)
