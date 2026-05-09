from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, DateTime, Enum
from sqlalchemy.orm import relationship
from ..core.database import Base
import enum
import uuid


class UserRole(str, enum.Enum):
    DEVELOPER = "developer"
    MANAGER = "manager"


class User(Base):
    __tablename__ = "users"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(UserRole, values_callable=lambda x: [e.value for e in x]), nullable=False, default=UserRole.DEVELOPER)
    total_score = Column(Float, default=0.0)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    merge_requests = relationship("MergeRequest", back_populates="author", passive_deletes=True)
    commits = relationship("Commit", back_populates="author", passive_deletes=True)
    review_comments = relationship("ReviewComment", back_populates="author", passive_deletes=True)
