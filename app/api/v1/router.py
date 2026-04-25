from fastapi import APIRouter
from app.api.v1 import auth, users, listings, messages, verify, scores

router = APIRouter()

router.include_router(auth.router)
router.include_router(users.router)
router.include_router(listings.router)
router.include_router(messages.router)
router.include_router(verify.router)
router.include_router(scores.router)
