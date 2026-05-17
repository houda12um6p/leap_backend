import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Enum, String
from sqlalchemy.orm import relationship

from ..core.database import Base


class ProjectStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class Project(Base):
    __tablename__ = "projects"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    repo_url = Column(String, nullable=False)
    jira_key = Column(String, nullable=True)
    jira_base_url = Column(String, nullable=True)
    jira_email = Column(String, nullable=True)
    jira_api_token_encrypted = Column(String, nullable=True)
    status = Column(Enum(ProjectStatus, values_callable=lambda x: [e.value for e in x]), nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    merge_requests = relationship("MergeRequest", back_populates="project", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="project", cascade="all, delete-orphan")
    jira_tasks = relationship("JiraTask", foreign_keys="[JiraTask.project_id]",
                               backref="project_ref", passive_deletes=True)

    @property
    def jira_api_token_set(self) -> bool:
        return bool(self.jira_api_token_encrypted)
