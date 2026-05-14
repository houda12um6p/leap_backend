from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MergeRequestBase(BaseModel):
    github_id: int | None = None
    title: str
    status: str
    score: float = 0.0
    story_points: int = 0
    refactored_lines: int = 0
    lines_modified: int = 0

class MergeRequestCreate(MergeRequestBase):
    author_id: str
    project_id: str
    jira_task_id: str | None = None


class MergeRequestUpdate(BaseModel):
    github_id: int | None = None
    title: str | None = None
    status: str | None = None
    score: float | None = None
    story_points: int | None = None
    refactored_lines: int | None = None
    lines_modified: int | None = None
    jira_task_id: str | None = None


class MergeRequestResponse(MergeRequestBase):
    id: str
    author_id: str
    project_id: str
    jira_task_id: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
