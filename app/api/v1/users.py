from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User, UserProfile
from app.schemas.user import UserOut, UserProfileUpdate
from app.schemas.common import ok, ResponseEnvelope

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=ResponseEnvelope[UserOut])
async def get_me(current_user: User = Depends(get_current_user)):
    return ok(current_user)


@router.patch("/me/profile", response_model=ResponseEnvelope[UserOut])
async def update_profile(body: UserProfileUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not current_user.profile:
        raise HTTPException(status_code=404, detail="Profil bulunamadı")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(current_user.profile, field, value)

    await db.commit()

    result = await db.execute(
        select(User).options(selectinload(User.profile)).where(User.id == current_user.id)
    )
    fresh = result.scalar_one()
    return ok(fresh)


@router.delete("/me", response_model=ResponseEnvelope[dict])
async def delete_account(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == current_user.id))
    profile = result.scalar_one_or_none()

    if profile:
        profile.full_name = "Silinmiş Kullanıcı"
        profile.bio = None
        profile.profile_photo_url = None
        profile.occupation = None

    current_user.is_deleted = True
    current_user.is_active = False
    current_user.deleted_at = datetime.now(timezone.utc)

    await db.commit()
    return ok({"message": "Hesabınız silindi"})


@router.get("/{user_id}", response_model=ResponseEnvelope[UserOut])
async def get_user(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User)
        .options(selectinload(User.profile))
        .where(User.id == user_id, User.is_deleted == False, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    return ok(user)
