import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..core.database import Base


class JiraTask(Base):
    __tablename__ = "jira_tasks"
    id           = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    jira_key     = Column(String, unique=True, nullable=False)
    summary      = Column(String, nullable=False)
    status       = Column(String, nullable=False)
    story_points = Column(Integer, default=0)
    project_id   = Column(String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    created_at   = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    updated_at   = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    merge_requests = relationship("MergeRequest", back_populates="jira_task")
