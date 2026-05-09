from pydantic import BaseModel
from ..models.commit import CommitType


class CommitBase(BaseModel):
    sha: str
    message: str
    date: str


class CommitCreate(CommitBase):
    author_id: str
    merge_request_id: str
class CommitResponse(CommitBase):
    author_id: str
    merge_request_id: str
    commit_type: CommitType
    class Config:
        from_attributes = True
