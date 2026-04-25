import os
import uuid
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.db.redis import get_redis
from app.dependencies import get_current_user
from app.models.user import User
from app.models.verification import VerificationRequest
from app.core.feature_flags import require_flag
from app.config import settings
from app.schemas.common import ok, ResponseEnvelope

router = APIRouter(prefix="/verify", tags=["verify"])

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@router.post("/id-document", response_model=ResponseEnvelope[dict])
async def upload_id_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Sadece JPEG, PNG veya WebP yükleyebilirsiniz")

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail=f"Dosya boyutu {settings.MAX_UPLOAD_SIZE_MB}MB'yi aşamaz")

    result = await db.execute(
        select(VerificationRequest).where(
            VerificationRequest.user_id == current_user.id,
            VerificationRequest.verify_type == "id_card",
            VerificationRequest.status.in_(["pending", "in_review"]),
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Zaten inceleme bekleyen bir doğrulama isteği var")

    upload_dir = os.path.join(settings.UPLOAD_DIR, "id_documents")
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{current_user.id}_{uuid.uuid4().hex}{os.path.splitext(file.filename or '.jpg')[1]}"
    filepath = os.path.join(upload_dir, filename)

    with open(filepath, "wb") as f:
        f.write(content)

    verification = VerificationRequest(
        user_id=current_user.id,
        verify_type="id_card",
        status="pending",
        document_url=filepath,
    )
    db.add(verification)
    await db.commit()

    return ok({"message": "Kimlik belgeniz incelemeye alındı. 24 saat içinde sonuçlandırılacak."})


@router.get("/status", response_model=ResponseEnvelope[list[dict]])
async def verification_status(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(VerificationRequest).where(VerificationRequest.user_id == current_user.id).order_by(VerificationRequest.created_at.desc())
    )
    records = result.scalars().all()
    return ok([{"type": r.verify_type, "status": r.status, "created_at": r.created_at} for r in records])


# V2 — Feature flag ile kapalı
@router.post("/face")
async def face_verify(db: AsyncSession = Depends(get_db)):
    await require_flag("face_recognition", db)


@router.post("/criminal-record")
async def criminal_record(db: AsyncSession = Depends(get_db)):
    await require_flag("criminal_record_llm", db)
