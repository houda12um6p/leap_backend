
from pydantic import BaseModel, ConfigDict


class JiraTaskBase(BaseModel):
    jira_key: str
    summary: str
    status: str
    story_points: int = 0


class JiraTaskCreate(JiraTaskBase):
    pass


class JiraTaskUpdate(BaseModel):
    jira_key: str | None = None
    summary: str | None = None
    status: str | None = None
    story_points: int | None = None

class JiraTaskResponse(JiraTaskBase):
    id: str
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)
