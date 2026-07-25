import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User, UserProfile
from app.models.house import House, HouseMembership, Expense, ExpenseSplit
from app.schemas.common import ok, ResponseEnvelope

router = APIRouter(prefix="/houses", tags=["houses"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class HouseCreate(BaseModel):
    name: str
    house_type: str = "apartment"
    city: str
    district: str
    neighborhood: Optional[str] = None
    address_detail: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    total_rooms: int = 1
    floor: Optional[int] = None
    size_sqm: Optional[int] = None
    rent_full: Optional[int] = None
    amenities: list[str] = []
    house_rules: dict = {}


class HouseUpdate(BaseModel):
    name: Optional[str] = None
    house_type: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    neighborhood: Optional[str] = None
    address_detail: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    total_rooms: Optional[int] = None
    floor: Optional[int] = None
    size_sqm: Optional[int] = None
    rent_full: Optional[int] = None
    amenities: Optional[list[str]] = None
    house_rules: Optional[dict] = None


class MemberInvite(BaseModel):
    user_id: str


class ExpenseCreate(BaseModel):
    title: str
    amount: float
    category: str = "other"
    expense_date: str  # ISO date string
    note: Optional[str] = None
    split_user_ids: list[str] = []  # who shares this expense (excluding payer)


class SettleRequest(BaseModel):
    expense_id: str
    user_id: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _house_out(house: House, memberships: list) -> dict:
    return {
        "id": str(house.id),
        "name": house.name,
        "house_type": house.house_type,
        "city": house.city,
        "district": house.district,
        "neighborhood": house.neighborhood,
        "address_detail": house.address_detail,
        "latitude": house.latitude,
        "longitude": house.longitude,
        "total_rooms": house.total_rooms,
        "floor": house.floor,
        "size_sqm": house.size_sqm,
        "rent_full": house.rent_full,
        "amenities": house.amenities,
        "house_rules": house.house_rules,
        "is_active": house.is_active,
        "owner_id": str(house.owner_id),
        "created_at": house.created_at.isoformat(),
        "members": memberships,
    }


def _member_out(m: HouseMembership) -> dict:
    profile = m.user.profile if m.user else None
    return {
        "id": str(m.id),
        "user_id": str(m.user_id),
        "role": m.role,
        "joined_at": m.joined_at.isoformat(),
        "left_at": m.left_at.isoformat() if m.left_at else None,
        "full_name": profile.full_name if profile else None,
        "profile_photo_url": profile.profile_photo_url if profile else None,
    }


def _expense_out(e: Expense) -> dict:
    payer_profile = e.payer.profile if e.payer else None
    return {
        "id": str(e.id),
        "house_id": str(e.house_id),
        "paid_by": str(e.paid_by),
        "payer_name": payer_profile.full_name if payer_profile else None,
        "payer_photo": payer_profile.profile_photo_url if payer_profile else None,
        "title": e.title,
        "amount": float(e.amount),
        "category": e.category,
        "expense_date": e.expense_date.isoformat(),
        "note": e.note,
        "created_at": e.created_at.isoformat(),
        "splits": [
            {
                "id": str(s.id),
                "user_id": str(s.user_id),
                "amount": float(s.amount),
                "is_settled": s.is_settled,
                "full_name": s.user.profile.full_name if s.user and s.user.profile else None,
            }
            for s in e.splits
        ],
    }


async def _require_member(house_id: str, user_id: uuid.UUID, db: AsyncSession) -> House:
    result = await db.execute(
        select(House)
        .options(
            selectinload(House.memberships).selectinload(HouseMembership.user).selectinload(User.profile),
        )
        .where(House.id == house_id, House.is_active == True)
    )
    house = result.scalar_one_or_none()
    if not house:
        raise HTTPException(status_code=404, detail="Ev bulunamadı")
    is_member = any(str(m.user_id) == str(user_id) and m.left_at is None for m in house.memberships)
    if not is_member:
        raise HTTPException(status_code=403, detail="Bu eve erişim yetkiniz yok")
    return house


async def _require_owner(house_id: str, user_id: uuid.UUID, db: AsyncSession) -> House:
    house = await _require_member(house_id, user_id, db)
    if str(house.owner_id) != str(user_id):
        raise HTTPException(status_code=403, detail="Yalnızca ev sahibi bu işlemi yapabilir")
    return house


# ── House CRUD ────────────────────────────────────────────────────────────────

@router.get("/my", response_model=ResponseEnvelope[list])
async def my_houses(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(House)
        .options(
            selectinload(House.memberships).selectinload(HouseMembership.user).selectinload(User.profile),
        )
        .join(HouseMembership, HouseMembership.house_id == House.id)
        .where(HouseMembership.user_id == current_user.id, HouseMembership.left_at == None, House.is_active == True)
        .order_by(House.created_at.desc())
    )
    houses = result.scalars().unique().all()
    return ok([_house_out(h, [_member_out(m) for m in h.memberships if m.left_at is None]) for h in houses])


@router.post("/", response_model=ResponseEnvelope[dict])
async def create_house(body: HouseCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    house = House(
        owner_id=current_user.id,
        name=body.name,
        house_type=body.house_type,
        city=body.city,
        district=body.district,
        neighborhood=body.neighborhood,
        address_detail=body.address_detail,
        latitude=body.latitude,
        longitude=body.longitude,
        total_rooms=body.total_rooms,
        floor=body.floor,
        size_sqm=body.size_sqm,
        rent_full=body.rent_full,
        amenities=body.amenities,
        house_rules=body.house_rules or {"smoking": False, "pets": False, "gender_preference": "any"},
    )
    db.add(house)
    await db.flush()

    membership = HouseMembership(house_id=house.id, user_id=current_user.id, role="owner")
    db.add(membership)
    await db.commit()
    await db.refresh(house)

    return ok({"id": str(house.id), "name": house.name})


@router.get("/{house_id}", response_model=ResponseEnvelope[dict])
async def get_house(house_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    house = await _require_member(house_id, current_user.id, db)
    members = [_member_out(m) for m in house.memberships if m.left_at is None]
    return ok(_house_out(house, members))


@router.patch("/{house_id}", response_model=ResponseEnvelope[dict])
async def update_house(house_id: str, body: HouseUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    house = await _require_owner(house_id, current_user.id, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(house, field, value)
    await db.commit()
    await db.refresh(house)
    members = [_member_out(m) for m in house.memberships if m.left_at is None]
    return ok(_house_out(house, members))


@router.delete("/{house_id}", response_model=ResponseEnvelope[dict])
async def deactivate_house(house_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    house = await _require_owner(house_id, current_user.id, db)
    house.is_active = False
    await db.commit()
    return ok({"message": "Ev devre dışı bırakıldı"})


# ── Members ───────────────────────────────────────────────────────────────────

@router.post("/{house_id}/members", response_model=ResponseEnvelope[dict])
async def add_member(house_id: str, body: MemberInvite, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    house = await _require_owner(house_id, current_user.id, db)

    result = await db.execute(select(User).where(User.id == body.user_id, User.is_deleted == False))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

    already = any(str(m.user_id) == body.user_id and m.left_at is None for m in house.memberships)
    if already:
        raise HTTPException(status_code=409, detail="Kullanıcı zaten bu evin üyesi")

    db.add(HouseMembership(house_id=house.id, user_id=uuid.UUID(body.user_id), role="tenant"))
    await db.commit()
    return ok({"message": "Üye eklendi"})


@router.delete("/{house_id}/members/{user_id}", response_model=ResponseEnvelope[dict])
async def remove_member(house_id: str, user_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    house = await _require_owner(house_id, current_user.id, db)
    if user_id == str(current_user.id):
        raise HTTPException(status_code=400, detail="Ev sahibi kendini çıkaramaz")

    membership = next((m for m in house.memberships if str(m.user_id) == user_id and m.left_at is None), None)
    if not membership:
        raise HTTPException(status_code=404, detail="Üye bulunamadı")

    membership.left_at = datetime.now(timezone.utc)
    await db.commit()
    return ok({"message": "Üye çıkarıldı"})


# ── Expenses ──────────────────────────────────────────────────────────────────

@router.get("/{house_id}/expenses", response_model=ResponseEnvelope[dict])
async def list_expenses(house_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _require_member(house_id, current_user.id, db)

    from datetime import date as date_type
    result = await db.execute(
        select(Expense)
        .options(
            selectinload(Expense.payer).selectinload(User.profile),
            selectinload(Expense.splits).selectinload(ExpenseSplit.user).selectinload(User.profile),
        )
        .where(Expense.house_id == house_id)
        .order_by(Expense.expense_date.desc(), Expense.created_at.desc())
    )
    expenses = result.scalars().all()

    # Calculate balances: who owes whom
    balances: dict[str, float] = {}
    for exp in expenses:
        payer_id = str(exp.paid_by)
        for split in exp.splits:
            if split.is_settled:
                continue
            uid = str(split.user_id)
            if uid == payer_id:
                continue
            # uid owes payer_id
            key = f"{uid}→{payer_id}"
            balances[key] = balances.get(key, 0) + float(split.amount)

    balance_list = [{"from_user": k.split("→")[0], "to_user": k.split("→")[1], "amount": round(v, 2)} for k, v in balances.items() if v > 0.01]

    return ok({
        "expenses": [_expense_out(e) for e in expenses],
        "balances": balance_list,
    })


@router.post("/{house_id}/expenses", response_model=ResponseEnvelope[dict])
async def create_expense(house_id: str, body: ExpenseCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    house = await _require_member(house_id, current_user.id, db)

    from datetime import date as date_type
    expense_date = date_type.fromisoformat(body.expense_date)
    amount = Decimal(str(body.amount))

    expense = Expense(
        house_id=uuid.UUID(house_id),
        paid_by=current_user.id,
        title=body.title,
        amount=amount,
        category=body.category,
        expense_date=expense_date,
        note=body.note,
    )
    db.add(expense)
    await db.flush()

    all_split_ids = list(set(body.split_user_ids + [str(current_user.id)]))
    share = round(amount / len(all_split_ids), 2)

    for uid in all_split_ids:
        settled = uid == str(current_user.id)
        db.add(ExpenseSplit(
            expense_id=expense.id,
            user_id=uuid.UUID(uid),
            amount=share,
            is_settled=settled,
        ))

    await db.commit()
    return ok({"id": str(expense.id)})


@router.delete("/{house_id}/expenses/{expense_id}", response_model=ResponseEnvelope[dict])
async def delete_expense(house_id: str, expense_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _require_member(house_id, current_user.id, db)

    result = await db.execute(select(Expense).where(Expense.id == expense_id, Expense.house_id == house_id))
    expense = result.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="Harcama bulunamadı")
    if str(expense.paid_by) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Yalnızca harcamayı ekleyen silebilir")

    await db.delete(expense)
    await db.commit()
    return ok({"message": "Harcama silindi"})


@router.patch("/{house_id}/expenses/{expense_id}/settle/{user_id}", response_model=ResponseEnvelope[dict])
async def settle_split(house_id: str, expense_id: str, user_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    house = await _require_member(house_id, current_user.id, db)

    result = await db.execute(select(Expense).where(Expense.id == expense_id, Expense.house_id == house_id))
    expense = result.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="Harcama bulunamadı")

    if str(expense.paid_by) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Yalnızca ödeyen kişi ödemeyi onaylayabilir")

    result2 = await db.execute(select(ExpenseSplit).where(ExpenseSplit.expense_id == expense_id, ExpenseSplit.user_id == user_id))
    split = result2.scalar_one_or_none()
    if not split:
        raise HTTPException(status_code=404, detail="Paylaşım bulunamadı")

    split.is_settled = True
    await db.commit()
    return ok({"message": "Ödeme onaylandı"})
