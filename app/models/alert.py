import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import relationship

from ..core.database import Base


class AlertSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    type = Column(String, nullable=False)
    severity = Column(Enum(AlertSeverity, values_callable=lambda x: [e.value for e in x]), nullable=False)
    message = Column(String, nullable=False)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    is_resolved = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(255), nullable=True)
    project = relationship("Project", back_populates="alerts")
