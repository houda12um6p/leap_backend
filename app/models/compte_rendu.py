import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from ..core.database import Base


class CompteRendu(Base):
    __tablename__ = "compte_rendus"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    raw_text = Column(Text, nullable=False)
    language = Column(String(5), default="fr")
    decisions = Column(Text, default="[]")   # JSON string
    actions = Column(Text, default="[]")     # JSON string
    blocages = Column(Text, default="[]")    # JSON string
    resume = Column(Text, default="")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    expires_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC) + timedelta(days=7))
    project = relationship("Project", backref="compte_rendus")
