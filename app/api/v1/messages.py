import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, update
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.message import Conversation, Message
from app.schemas.message import MessageCreate
from app.schemas.common import ok, ResponseEnvelope

router = APIRouter(prefix="/messages", tags=["messages"])


def _msg_out(m: Message) -> dict:
    return {
        "id": str(m.id),
        "conversation_id": str(m.conversation_id),
        "sender_id": str(m.sender_id),
        "content": m.content,
        "is_read": m.is_read,
        "created_at": m.created_at.isoformat(),
    }


async def _conv_out(conv: Conversation, current_user_id: uuid.UUID, db: AsyncSession) -> dict:
    other_id = conv.participant_b if conv.participant_a == current_user_id else conv.participant_a
    other_result = await db.execute(
        select(User).options(selectinload(User.profile)).where(User.id == other_id)
    )
    other = other_result.scalar_one_or_none()

    msgs_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    last_msg = msgs_result.scalar_one_or_none()

    unread_result = await db.execute(
        select(Message).where(
            Message.conversation_id == conv.id,
            Message.sender_id != current_user_id,
            Message.is_read == False,
        )
    )
    unread_count = len(unread_result.scalars().all())

    return {
        "id": str(conv.id),
        "listing_id": str(conv.listing_id) if conv.listing_id else None,
        "created_at": conv.created_at.isoformat(),
        "other_user": {
            "id": str(other.id),
            "full_name": other.profile.full_name if other and other.profile else None,
            "profile_photo_url": other.profile.profile_photo_url if other and other.profile else None,
        } if other else {"id": str(other_id), "full_name": None, "profile_photo_url": None},
        "last_message": _msg_out(last_msg) if last_msg else None,
        "unread_count": unread_count,
    }


@router.get("/conversations", response_model=ResponseEnvelope[list])
async def list_conversations(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Conversation)
        .where(or_(Conversation.participant_a == current_user.id, Conversation.participant_b == current_user.id))
        .order_by(Conversation.created_at.desc())
    )
    conversations = result.scalars().all()
    output = [await _conv_out(c, current_user.id, db) for c in conversations]
    return ok(output)


@router.post("/conversations", response_model=ResponseEnvelope[dict])
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
        return ok(await _conv_out(existing, current_user.id, db))

    conv = Conversation(participant_a=current_user.id, participant_b=other_user_id, listing_id=listing_id)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return ok(await _conv_out(conv, current_user.id, db))


@router.get("/conversations/{conversation_id}/messages", response_model=ResponseEnvelope[list])
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

    # Mark incoming messages as read
    await db.execute(
        update(Message)
        .where(Message.conversation_id == conversation_id, Message.sender_id != current_user.id, Message.is_read == False)
        .values(is_read=True)
    )
    await db.commit()

    msgs_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return ok([_msg_out(m) for m in msgs_result.scalars().all()])


@router.post("/conversations/{conversation_id}/messages", response_model=ResponseEnvelope[dict])
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

    if not body.content.strip():
        raise HTTPException(status_code=400, detail="Mesaj boş olamaz")

    msg = Message(conversation_id=conversation_id, sender_id=current_user.id, content=body.content.strip())
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return ok(_msg_out(msg))
