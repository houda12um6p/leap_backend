from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..models.commit import Commit
from ..models.merge_request import MergeRequest
from ..models.project import Project
from ..models.review_comment import ReviewComment
from ..models.user import User

router = APIRouter(tags=["merge_requests"])


def _serialize_mr_summary(mr: MergeRequest, author: User | None) -> Dict[str, Any]:
    return {
        "id": str(mr.id),
        "github_id": mr.github_id,
        "title": mr.title,
        "status": mr.status.value if hasattr(mr.status, "value") else mr.status,
        "score": mr.score or 0.0,
        "story_points": mr.story_points or 0,
        "refactored_lines": mr.refactored_lines or 0,
        "lines_modified": mr.lines_modified or 0,
        "author_id": mr.author_id,
        "author_name": author.name if author else None,
        "author_email": author.email if author else None,
        "project_id": mr.project_id,
        "jira_task_id": mr.jira_task_id,
        "jira_key": mr.jira_task.jira_key if mr.jira_task else None,
        "created_at": mr.created_at.isoformat() if mr.created_at else None,
        "updated_at": mr.updated_at.isoformat() if mr.updated_at else None,
    }


@router.get("/projects/{project_id}/merge-requests")
def list_project_merge_requests(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    mrs = (
        db.query(MergeRequest)
        .filter(MergeRequest.project_id == project_id)
        .order_by(MergeRequest.updated_at.desc())
        .all()
    )
    author_ids = {mr.author_id for mr in mrs if mr.author_id}
    authors: Dict[str, User] = {}
    if author_ids:
        for u in db.query(User).filter(User.id.in_(author_ids)).all():
            authors[u.id] = u
    return [_serialize_mr_summary(mr, authors.get(mr.author_id)) for mr in mrs]


@router.get("/merge-requests/{mr_id}")
def get_merge_request(
    mr_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    mr = db.query(MergeRequest).filter(MergeRequest.id == mr_id).first()
    if not mr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Merge request not found")

    author = db.query(User).filter(User.id == mr.author_id).first() if mr.author_id else None

    commit_rows = (
        db.query(Commit)
        .filter(Commit.merge_request_id == mr_id)
        .order_by(Commit.date.desc())
        .all()
    )
    commit_authors: Dict[str, User] = {}
    commit_author_ids = {c.author_id for c in commit_rows if c.author_id}
    if commit_author_ids:
        for u in db.query(User).filter(User.id.in_(commit_author_ids)).all():
            commit_authors[u.id] = u
    commits = []
    for c in commit_rows:
        ca = commit_authors.get(c.author_id) if c.author_id else None
        commits.append({
            "sha": c.sha,
            "message": c.message,
            "date": c.date.isoformat() if c.date else None,
            "author_id": c.author_id,
            "author_name": ca.name if ca else None,
            "commit_type": c.analyze_message().value,
        })

    review_rows = (
        db.query(ReviewComment)
        .filter(ReviewComment.merge_request_id == mr_id)
        .order_by(ReviewComment.created_at.desc())
        .all()
    )
    review_author_ids = {r.author_id for r in review_rows if r.author_id}
    review_authors: Dict[str, User] = {}
    if review_author_ids:
        for u in db.query(User).filter(User.id.in_(review_author_ids)).all():
            review_authors[u.id] = u
    review_comments = []
    for r in review_rows:
        ra = review_authors.get(r.author_id) if r.author_id else None
        review_comments.append({
            "id": str(r.id),
            "body": r.body,
            "severity_weight": r.severity_weight or 0,
            "author_id": r.author_id,
            "author_name": ra.name if ra else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    summary = _serialize_mr_summary(mr, author)
    summary["commits"] = commits
    summary["review_comments"] = review_comments
    return summary
