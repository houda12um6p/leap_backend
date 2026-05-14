import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class ProjectBase(BaseModel):
    name: str
    repo_url: str
    status: str = "active"

    @field_validator("repo_url")
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        pattern = r'^https?://(www\.)?github\.com/[\w.\-]+/[\w.\-]+$'
        if not re.match(pattern, v):
            raise ValueError(
                "repo_url must be a valid GitHub repository URL "
                "(e.g. https://github.com/owner/repo)"
            )
        return v.rstrip('/')

    @field_validator("status", mode="before")
    @classmethod
    def normalise_status(cls, v: str) -> str:
        return v.lower()


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: str | None = None
    repo_url: str | None = None
    status: str | None = None


class ProjectResponse(ProjectBase):
    id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
