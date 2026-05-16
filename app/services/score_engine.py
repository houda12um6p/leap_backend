"""
Scoring engine for merge requests, developers, and projects.

Per-MR formula:
    Score = 1000 × e^(-0.07 × max(0, Xnorm - delta))
        X     = sum of severity_weight across review comments
        L     = lines_modified
        Xnorm = X / sqrt(1 + L)
        delta = story points from linked Jira task

Aggregates:
    Developer score = SUM of that developer's MR scores (can exceed 1000)
    Project   score = mean of all MR scores in the project (0..1000)

Means keep the aggregate on the same 0..1000 scale as a single MR,
so a project with 4 PRs and one with 40 PRs are directly comparable.
"""

import math

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models.alert import Alert, AlertSeverity
from ..models.merge_request import MergeRequest
from ..models.review_comment import ReviewComment
from ..models.user import User

k: float = 0.07


def calculate_mr_score(mr_id: str, db: Session) -> float:
    mr = db.query(MergeRequest).filter(MergeRequest.id == mr_id).first()
    if not mr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MergeRequest {mr_id} not found",
        )

    comments = (
        db.query(ReviewComment)
        .filter(ReviewComment.merge_request_id == mr_id)
        .all()
    )
    X = sum(c.severity_weight for c in comments)
    L = mr.lines_modified or 0
    Xnorm = X / math.sqrt(1 + L)
    delta = mr.jira_task.story_points if mr.jira_task else 0

    x = max(0.0, Xnorm - delta)
    score = round(1000 * math.exp(-k * x), 2)

    mr.score = score
    db.commit()
    return score


def calculate_developer_score(user_id: str, db: Session, project_id: str | None = None) -> float:
    """Sum of this developer's MR scores. Persists to User.total_score.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )

    if project_id:
        mrs = (
            db.query(MergeRequest)
            .filter(
                MergeRequest.author_id == user_id,
                MergeRequest.project_id == project_id,
            )
            .all()
        )
    else:
        mrs = (
            db.query(MergeRequest)
            .filter(MergeRequest.author_id == user_id)
            .all()
        )
    if not mrs:
        user.total_score = 0.0
        db.commit()
        return 0.0

    total = round(sum(mr.score or 0.0 for mr in mrs), 2)
    user.total_score = total
    db.commit()

    avg_score = round(total / len(mrs), 2)
    if avg_score < 700 and project_id:
        _ensure_low_score_alert(db, user, avg_score, project_id)

    return total


def _ensure_low_score_alert(db: Session, user: User, score: float, project_id: str) -> None:
    """Create a high alert if no open low-score alert exists for this dev+project."""
    existing = (
        db.query(Alert)
        .filter(
            Alert.project_id == project_id,
            Alert.type == "low_developer_score",
            Alert.message.like(f"%{user.email}%"),
            Alert.is_resolved == False,
        )
        .first()
    )
    if existing:
        return

    db.add(Alert(
        type="low_developer_score",
        severity=AlertSeverity.HIGH,
        message=f"{user.name} ({user.email}) average PR score is {score:.0f} — quality review needed",
        project_id=project_id,
        is_resolved=False,
    ))
    db.commit()


def calculate_project_score(project_id: str, db: Session) -> float:
    """Recalculate every MR + developer in the project. Returns mean MR score."""
    mrs = (
        db.query(MergeRequest)
        .filter(MergeRequest.project_id == project_id)
        .all()
    )
    mr_scores = [calculate_mr_score(mr.id, db) for mr in mrs]

    author_ids = {mr.author_id for mr in mrs if mr.author_id}
    for user_id in author_ids:
        calculate_developer_score(user_id, db, project_id=project_id)

    if not mr_scores:
        return 0.0
    return round(sum(mr_scores) / len(mr_scores), 2)
