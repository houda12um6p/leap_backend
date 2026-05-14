from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReviewCommentBase(BaseModel):
    body: str
    # 0 = suggestion, 1 = minor issue, 3 = correctness bug, 5 = critical issue
    severity_weight: int = 0


class ReviewCommentCreate(ReviewCommentBase):
    author_id: str
    merge_request_id: str


class ReviewCommentUpdate(BaseModel):
    body: str | None = None
    severity_weight: int | None = None


class ReviewCommentResponse(ReviewCommentBase):
    id: str
    author_id: str
    merge_request_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
