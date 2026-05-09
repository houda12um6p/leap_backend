import re
from datetime import datetime
from pydantic import BaseModel, field_validator
from typing import Optional

class ProjectBase(BaseModel):
    name: str
    repo_url: str
    status: str = "active"

    @field_validator("repo_url")
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        if not re.search(r'github\.com[/:][\w.\-]+/[\w.\-]+', v):
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
    name: Optional[str] = None
    repo_url: Optional[str] = None
    status: Optional[str] = None


class ProjectResponse(ProjectBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True
