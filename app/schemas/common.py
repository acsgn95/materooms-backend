from typing import Generic, TypeVar, Optional
from pydantic import BaseModel

T = TypeVar("T")


class ErrorDetail(BaseModel):
    code: str
    message: str


class PaginationMeta(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int


class ResponseEnvelope(BaseModel, Generic[T]):
    success: bool
    data: Optional[T] = None
    error: Optional[ErrorDetail] = None
    meta: Optional[PaginationMeta] = None


def ok(data: T, meta: PaginationMeta | None = None) -> ResponseEnvelope[T]:
    return ResponseEnvelope(success=True, data=data, meta=meta)


def err(code: str, message: str) -> ResponseEnvelope:
    return ResponseEnvelope(success=False, error=ErrorDetail(code=code, message=message))
