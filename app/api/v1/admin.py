import psutil
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from typing import Optional

from app.db.session import get_db
from app.config import settings
from app.models.user import User, UserProfile
from app.models.listing import Listing

router = APIRouter(prefix="/admin", tags=["admin"])


def verify_admin(x_admin_secret: str = Header(...)):
    if x_admin_secret != settings.ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("/stats", dependencies=[Depends(verify_admin)])
async def get_stats(db: AsyncSession = Depends(get_db)):
    total_users = await db.scalar(select(func.count()).select_from(User).where(User.is_deleted == False))
    active_users = await db.scalar(select(func.count()).select_from(User).where(User.is_active == True, User.is_deleted == False))
    total_listings = await db.scalar(select(func.count()).select_from(Listing))
    active_listings = await db.scalar(select(func.count()).select_from(Listing).where(Listing.is_active == True))

    return {
        "users": {"total": total_users, "active": active_users},
        "listings": {"total": total_listings, "active": active_listings},
    }


@router.get("/users", dependencies=[Depends(verify_admin)])
async def list_users(
    page: int = 1,
    limit: int = 20,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * limit
    query = (
        select(User, UserProfile)
        .outerjoin(UserProfile, User.id == UserProfile.user_id)
        .where(User.is_deleted == False)
    )
    if search:
        query = query.where(User.phone.ilike(f"%{search}%"))

    count_query = select(func.count()).select_from(User).where(User.is_deleted == False)
    if search:
        count_query = count_query.where(User.phone.ilike(f"%{search}%"))

    total = await db.scalar(count_query)
    result = await db.execute(query.order_by(User.created_at.desc()).offset(offset).limit(limit))
    rows = result.all()

    users = []
    for user, profile in rows:
        users.append({
            "id": str(user.id),
            "phone": user.phone,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat(),
            "full_name": profile.full_name if profile else None,
            "city": profile.city if profile else None,
            "verification_badges": profile.verification_badges if profile else [],
        })

    return {"users": users, "total": total, "page": page, "limit": limit}


@router.patch("/users/{user_id}/toggle", dependencies=[Depends(verify_admin)])
async def toggle_user(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = not user.is_active
    await db.commit()
    return {"id": str(user.id), "is_active": user.is_active}


@router.delete("/users/{user_id}", dependencies=[Depends(verify_admin)])
async def delete_user(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_deleted = True
    user.is_active = False
    await db.commit()
    return {"success": True}


@router.get("/listings", dependencies=[Depends(verify_admin)])
async def list_listings(
    page: int = 1,
    limit: int = 20,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * limit
    query = select(Listing)
    if search:
        query = query.where(Listing.title.ilike(f"%{search}%"))

    count_query = select(func.count()).select_from(Listing)
    if search:
        count_query = count_query.where(Listing.title.ilike(f"%{search}%"))

    total = await db.scalar(count_query)
    result = await db.execute(query.order_by(Listing.created_at.desc()).offset(offset).limit(limit))
    listings = result.scalars().all()

    return {
        "listings": [
            {
                "id": str(l.id),
                "title": l.title,
                "city": l.city,
                "district": l.district,
                "listing_type": l.listing_type,
                "rent_full": l.rent_full,
                "is_active": l.is_active,
                "created_at": l.created_at.isoformat(),
            }
            for l in listings
        ],
        "total": total,
        "page": page,
        "limit": limit,
    }


@router.patch("/listings/{listing_id}/toggle", dependencies=[Depends(verify_admin)])
async def toggle_listing(listing_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    listing.is_active = not listing.is_active
    await db.commit()
    return {"id": str(listing.id), "is_active": listing.is_active}


@router.delete("/listings/{listing_id}", dependencies=[Depends(verify_admin)])
async def delete_listing(listing_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    await db.delete(listing)
    await db.commit()
    return {"success": True}


@router.get("/system", dependencies=[Depends(verify_admin)])
async def get_system():
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return {
        "cpu_percent": cpu,
        "ram": {
            "total_gb": round(ram.total / 1024**3, 2),
            "used_gb": round(ram.used / 1024**3, 2),
            "percent": ram.percent,
        },
        "disk": {
            "total_gb": round(disk.total / 1024**3, 2),
            "used_gb": round(disk.used / 1024**3, 2),
            "percent": disk.percent,
        },
    }
