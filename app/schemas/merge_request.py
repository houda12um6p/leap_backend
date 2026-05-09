from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class MergeRequestBase(BaseModel):
    github_id: Optional[int] = None
    title: str
    status: str
    score: float = 0.0
    story_points: int = 0
    refactored_lines: int = 0
    lines_modified: int = 0

class MergeRequestCreate(MergeRequestBase):
    author_id: str
    project_id: str
    jira_task_id: Optional[str] = None


class MergeRequestUpdate(BaseModel):
    github_id: Optional[int] = None
    title: Optional[str] = None
    status: Optional[str] = None
    score: Optional[float] = None
    story_points: Optional[int] = None
    refactored_lines: Optional[int] = None
    lines_modified: Optional[int] = None
    jira_task_id: Optional[str] = None


class MergeRequestResponse(MergeRequestBase):
    id: str
    author_id: str
    project_id: str
    jira_task_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
