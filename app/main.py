from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.db.redis import close_redis
from app.api.v1.router import router as v1_router
from app.core.telegram import notify_api_error


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_redis()


app = FastAPI(
    title="MateRooms API",
    version="1.0.0",
    description="Turkey's Verified Flatmate Platform",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"https://(.*\.vercel\.app|(www\.)?materooms\.com)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def error_notification_middleware(request: Request, call_next):
    response = await call_next(request)
    if response.status_code >= 500:
        await notify_api_error(str(request.url.path), response.status_code, "Sunucu hatası")
    return response

app.include_router(v1_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
