import uuid
import secrets
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.house import Group, GroupMembership, Expense, ExpenseSplit
from app.schemas.common import ok, ResponseEnvelope

router = APIRouter(prefix="/groups", tags=["groups"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class MemberInvite(BaseModel):
    user_id: str


class ExpenseCreate(BaseModel):
    title: str
    amount: float
    category: str = "other"
    expense_date: str  # ISO date string
    note: Optional[str] = None
    split_user_ids: list[str] = []


# ── Helpers ───────────────────────────────────────────────────────────────────

def _group_out(group: Group) -> dict:
    active_members = [m for m in group.memberships if m.left_at is None]
    return {
        "id": str(group.id),
        "owner_id": str(group.owner_id),
        "name": group.name,
        "description": group.description,
        "invite_code": group.invite_code,
        "is_active": group.is_active,
        "created_at": group.created_at.isoformat(),
        "member_count": len(active_members),
        "members": [_member_out(m) for m in active_members],
    }


def _member_out(m: GroupMembership) -> dict:
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
        "group_id": str(e.group_id),
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


async def _load_group(group_id: str, db: AsyncSession) -> Group:
    result = await db.execute(
        select(Group)
        .options(
            selectinload(Group.memberships).selectinload(GroupMembership.user).selectinload(User.profile),
        )
        .where(Group.id == group_id, Group.is_active == True)
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Grup bulunamadı")
    return group


async def _require_member(group_id: str, user_id: uuid.UUID, db: AsyncSession) -> Group:
    group = await _load_group(group_id, db)
    is_member = any(str(m.user_id) == str(user_id) and m.left_at is None for m in group.memberships)
    if not is_member:
        raise HTTPException(status_code=403, detail="Bu gruba erişim yetkiniz yok")
    return group


async def _require_owner(group_id: str, user_id: uuid.UUID, db: AsyncSession) -> Group:
    group = await _require_member(group_id, user_id, db)
    if str(group.owner_id) != str(user_id):
        raise HTTPException(status_code=403, detail="Yalnızca grup sahibi bu işlemi yapabilir")
    return group


# ── Group CRUD ────────────────────────────────────────────────────────────────

@router.get("/my", response_model=ResponseEnvelope[list])
async def my_groups(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Group)
        .options(
            selectinload(Group.memberships).selectinload(GroupMembership.user).selectinload(User.profile),
        )
        .join(GroupMembership, GroupMembership.group_id == Group.id)
        .where(GroupMembership.user_id == current_user.id, GroupMembership.left_at == None, Group.is_active == True)
        .order_by(Group.created_at.desc())
    )
    groups = result.scalars().unique().all()
    return ok([_group_out(g) for g in groups])


@router.post("/", response_model=ResponseEnvelope[dict])
async def create_group(body: GroupCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    group = Group(
        owner_id=current_user.id,
        name=body.name,
        description=body.description,
    )
    db.add(group)
    await db.flush()

    membership = GroupMembership(group_id=group.id, user_id=current_user.id, role="owner")
    db.add(membership)
    await db.commit()
    await db.refresh(group)

    return ok({"id": str(group.id), "name": group.name})


@router.get("/{group_id}", response_model=ResponseEnvelope[dict])
async def get_group(group_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    group = await _require_member(group_id, current_user.id, db)
    return ok(_group_out(group))


@router.patch("/{group_id}", response_model=ResponseEnvelope[dict])
async def update_group(group_id: str, body: GroupUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    group = await _require_owner(group_id, current_user.id, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(group, field, value)
    await db.commit()
    await db.refresh(group)
    return ok(_group_out(group))


@router.delete("/{group_id}", response_model=ResponseEnvelope[dict])
async def deactivate_group(group_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    group = await _require_owner(group_id, current_user.id, db)
    group.is_active = False
    await db.commit()
    return ok({"message": "Grup kapatıldı"})


# ── Invite code ───────────────────────────────────────────────────────────────

@router.post("/{group_id}/invite", response_model=ResponseEnvelope[dict])
async def generate_invite(group_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    group = await _require_owner(group_id, current_user.id, db)
    group.invite_code = secrets.token_urlsafe(8)
    await db.commit()
    return ok({"invite_code": group.invite_code})


@router.post("/join/{invite_code}", response_model=ResponseEnvelope[dict])
async def join_by_invite(invite_code: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Group)
        .options(selectinload(Group.memberships))
        .where(Group.invite_code == invite_code, Group.is_active == True)
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Geçersiz davet kodu")

    already = any(str(m.user_id) == str(current_user.id) and m.left_at is None for m in group.memberships)
    if already:
        raise HTTPException(status_code=409, detail="Zaten bu grubun üyesisin")

    db.add(GroupMembership(group_id=group.id, user_id=current_user.id, role="member"))
    await db.commit()
    return ok({"group_id": str(group.id), "name": group.name})


# ── Members ───────────────────────────────────────────────────────────────────

@router.post("/{group_id}/members", response_model=ResponseEnvelope[dict])
async def add_member(group_id: str, body: MemberInvite, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    group = await _require_owner(group_id, current_user.id, db)

    result = await db.execute(select(User).where(User.id == body.user_id, User.is_deleted == False))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

    already = any(str(m.user_id) == body.user_id and m.left_at is None for m in group.memberships)
    if already:
        raise HTTPException(status_code=409, detail="Kullanıcı zaten bu grubun üyesi")

    db.add(GroupMembership(group_id=group.id, user_id=uuid.UUID(body.user_id), role="member"))
    await db.commit()
    return ok({"message": "Üye eklendi"})


@router.delete("/{group_id}/members/{user_id}", response_model=ResponseEnvelope[dict])
async def remove_member(group_id: str, user_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    group = await _require_owner(group_id, current_user.id, db)
    if user_id == str(current_user.id):
        raise HTTPException(status_code=400, detail="Grup sahibi kendini çıkaramaz")

    membership = next((m for m in group.memberships if str(m.user_id) == user_id and m.left_at is None), None)
    if not membership:
        raise HTTPException(status_code=404, detail="Üye bulunamadı")

    membership.left_at = datetime.now(timezone.utc)
    await db.commit()
    return ok({"message": "Üye çıkarıldı"})


# ── Expenses ──────────────────────────────────────────────────────────────────

@router.get("/{group_id}/expenses", response_model=ResponseEnvelope[dict])
async def list_expenses(group_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _require_member(group_id, current_user.id, db)

    result = await db.execute(
        select(Expense)
        .options(
            selectinload(Expense.payer).selectinload(User.profile),
            selectinload(Expense.splits).selectinload(ExpenseSplit.user).selectinload(User.profile),
        )
        .where(Expense.group_id == group_id)
        .order_by(Expense.expense_date.desc(), Expense.created_at.desc())
    )
    expenses = result.scalars().all()

    balances: dict[str, float] = {}
    for exp in expenses:
        payer_id = str(exp.paid_by)
        for split in exp.splits:
            if split.is_settled:
                continue
            uid = str(split.user_id)
            if uid == payer_id:
                continue
            key = f"{uid}→{payer_id}"
            balances[key] = balances.get(key, 0) + float(split.amount)

    balance_list = [
        {"from_user": k.split("→")[0], "to_user": k.split("→")[1], "amount": round(v, 2)}
        for k, v in balances.items() if v > 0.01
    ]

    return ok({"expenses": [_expense_out(e) for e in expenses], "balances": balance_list})


@router.post("/{group_id}/expenses", response_model=ResponseEnvelope[dict])
async def create_expense(group_id: str, body: ExpenseCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _require_member(group_id, current_user.id, db)

    from datetime import date as date_type
    expense_date = date_type.fromisoformat(body.expense_date)
    amount = Decimal(str(body.amount))

    expense = Expense(
        group_id=uuid.UUID(group_id),
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
        db.add(ExpenseSplit(
            expense_id=expense.id,
            user_id=uuid.UUID(uid),
            amount=share,
            is_settled=(uid == str(current_user.id)),
        ))

    await db.commit()
    return ok({"id": str(expense.id)})


@router.delete("/{group_id}/expenses/{expense_id}", response_model=ResponseEnvelope[dict])
async def delete_expense(group_id: str, expense_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _require_member(group_id, current_user.id, db)

    result = await db.execute(select(Expense).where(Expense.id == expense_id, Expense.group_id == group_id))
    expense = result.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="Harcama bulunamadı")
    if str(expense.paid_by) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Yalnızca harcamayı ekleyen silebilir")

    await db.delete(expense)
    await db.commit()
    return ok({"message": "Harcama silindi"})


@router.patch("/{group_id}/expenses/{expense_id}/settle/{user_id}", response_model=ResponseEnvelope[dict])
async def settle_split(group_id: str, expense_id: str, user_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _require_member(group_id, current_user.id, db)

    result = await db.execute(select(Expense).where(Expense.id == expense_id, Expense.group_id == group_id))
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
