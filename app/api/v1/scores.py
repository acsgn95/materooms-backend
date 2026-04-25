import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.score import FlatmateScore, ScoreEvent
from app.schemas.score import ScoreOut
from app.schemas.common import ok, ResponseEnvelope

router = APIRouter(prefix="/scores", tags=["scores"])


@router.get("/me", response_model=ResponseEnvelope[ScoreOut])
async def get_my_score(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FlatmateScore).where(FlatmateScore.user_id == current_user.id))
    score = result.scalar_one_or_none()
    if not score:
        raise HTTPException(status_code=404, detail="Skor bulunamadı")

    events_result = await db.execute(
        select(ScoreEvent).where(ScoreEvent.user_id == current_user.id).order_by(ScoreEvent.created_at.desc()).limit(20)
    )
    score_out = ScoreOut.model_validate(score)
    score_out.recent_events = events_result.scalars().all()
    return ok(score_out)


@router.get("/{user_id}", response_model=ResponseEnvelope[ScoreOut])
async def get_user_score(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FlatmateScore).where(FlatmateScore.user_id == user_id))
    score = result.scalar_one_or_none()
    if not score:
        raise HTTPException(status_code=404, detail="Skor bulunamadı")

    score_out = ScoreOut.model_validate(score)
    score_out.recent_events = []
    return ok(score_out)
