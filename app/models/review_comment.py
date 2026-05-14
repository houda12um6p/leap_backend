import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..core.database import Base


class ReviewComment(Base):
    __tablename__ = "review_comments"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    body = Column(String, nullable=False)
    # Severity weight assigned by the LLM classifier:
    #   0 = suggestion (no penalty)
    #   1 = minor issue
    #   3 = correctness bug
    #   5 = critical issue
    severity_weight = Column(Integer, default=0)
    author_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    merge_request_id = Column(String(36), ForeignKey("merge_requests.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    author = relationship("User", back_populates="review_comments")
    merge_request = relationship("MergeRequest", back_populates="review_comments")

    def detect_problem(self) -> bool:
        problem_keywords = [
            'bug', 'error', 'issue', 'problem', 'fix', 'broken',
            'wrong', 'incorrect', 'fail', 'crash', 'exception'
        ]
        body_lower = self.body.lower()
        return any(keyword in body_lower for keyword in problem_keywords)
