from pydantic import BaseModel
from typing import Optional


class JiraTaskBase(BaseModel):
    jira_key: str
    summary: str
    status: str
    story_points: int = 0


class JiraTaskCreate(JiraTaskBase):
    pass


class JiraTaskUpdate(BaseModel):
    jira_key: Optional[str] = None
    summary: Optional[str] = None
    status: Optional[str] = None
    story_points: Optional[int] = None

class JiraTaskResponse(JiraTaskBase):
    id: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True
