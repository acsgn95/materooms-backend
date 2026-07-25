from fastapi import APIRouter
from app.api.v1 import auth, users, listings, messages, verify, scores, admin, houses

router = APIRouter()

router.include_router(auth.router)
router.include_router(users.router)
router.include_router(listings.router)
router.include_router(messages.router)
router.include_router(verify.router)
router.include_router(scores.router)
router.include_router(admin.router)
router.include_router(houses.router)
