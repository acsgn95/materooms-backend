import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.listing import Listing
from app.models.score import FlatmateScore
from app.schemas.listing import ListingCreate, ListingUpdate, ListingOut, ListingOwnerBrief
from app.schemas.common import ok, ResponseEnvelope, PaginationMeta

router = APIRouter(prefix="/listings", tags=["listings"])


async def _build_listing_out(listing: Listing, db: AsyncSession) -> ListingOut:
    owner_brief: ListingOwnerBrief | None = None
    user = listing.user
    if user:
        score_row = await db.execute(
            select(FlatmateScore.total_score).where(FlatmateScore.user_id == user.id)
        )
        flatmate_score = score_row.scalar()
        owner_brief = ListingOwnerBrief(
            id=user.id,
            full_name=user.profile.full_name if user.profile else None,
            profile_photo_url=user.profile.profile_photo_url if user.profile else None,
            verification_badges=user.profile.verification_badges if user.profile else [],
            flatmate_score=flatmate_score,
        )
    base = ListingOut.model_validate(listing)
    base.owner = owner_brief
    return base


def _listing_query_with_owner():
    return select(Listing).options(
        selectinload(Listing.user).selectinload(User.profile),
        selectinload(Listing.photos),
    )


@router.post("/", response_model=ResponseEnvelope[ListingOut])
async def create_listing(body: ListingCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    listing = Listing(
        **body.model_dump(),
        user_id=current_user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=60),
    )
    db.add(listing)
    await db.commit()

    result = await db.execute(_listing_query_with_owner().where(Listing.id == listing.id))
    fresh = result.scalar_one()
    return ok(await _build_listing_out(fresh, db))


@router.get("/", response_model=ResponseEnvelope[list[ListingOut]])
async def list_listings(
    city: str | None = Query(None),
    district: str | None = Query(None),
    listing_type: str | None = Query(None),
    budget_max: int | None = Query(None),
    budget_min: int | None = Query(None),
    user_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    filters = [Listing.is_active == True, Listing.expires_at > datetime.now(timezone.utc)]

    if city:
        filters.append(Listing.city == city)
    if district:
        filters.append(Listing.district == district)
    if listing_type:
        filters.append(Listing.listing_type == listing_type)
    if budget_max:
        filters.append(Listing.rent_full <= budget_max)
    if budget_min:
        filters.append(Listing.rent_full >= budget_min)
    if user_id:
        filters.append(Listing.user_id == user_id)

    count_result = await db.execute(select(func.count()).select_from(Listing).where(and_(*filters)))
    total = count_result.scalar() or 0

    result = await db.execute(
        _listing_query_with_owner()
        .where(and_(*filters))
        .order_by(Listing.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    listings = result.scalars().all()

    out = [await _build_listing_out(l, db) for l in listings]
    meta = PaginationMeta(total=total, page=page, page_size=page_size, total_pages=(total + page_size - 1) // page_size)
    return ok(out, meta=meta)


@router.get("/{listing_id}", response_model=ResponseEnvelope[ListingOut])
async def get_listing(listing_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(_listing_query_with_owner().where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="İlan bulunamadı")
    return ok(await _build_listing_out(listing, db))


@router.patch("/{listing_id}", response_model=ResponseEnvelope[ListingOut])
async def update_listing(listing_id: uuid.UUID, body: ListingUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        _listing_query_with_owner().where(Listing.id == listing_id, Listing.user_id == current_user.id)
    )
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="İlan bulunamadı veya yetkiniz yok")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(listing, field, value)

    await db.commit()
    await db.refresh(listing)
    return ok(await _build_listing_out(listing, db))


@router.delete("/{listing_id}", response_model=ResponseEnvelope[dict])
async def delete_listing(listing_id: uuid.UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Listing).where(Listing.id == listing_id, Listing.user_id == current_user.id))
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="İlan bulunamadı veya yetkiniz yok")

    listing.is_active = False
    await db.commit()
    return ok({"message": "İlan kaldırıldı"})
