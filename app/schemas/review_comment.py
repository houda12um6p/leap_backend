from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class ReviewCommentBase(BaseModel):
    body: str
    # 0 = suggestion, 1 = minor issue, 3 = correctness bug, 5 = critical issue
    severity_weight: int = 0


class ReviewCommentCreate(ReviewCommentBase):
    author_id: str
    merge_request_id: str


class ReviewCommentUpdate(BaseModel):
    body: Optional[str] = None
    severity_weight: Optional[int] = None


class ReviewCommentResponse(ReviewCommentBase):
    id: str
    author_id: str
    merge_request_id: str
    created_at: datetime

    class Config:
        from_attributes = True
