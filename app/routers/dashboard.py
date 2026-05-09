from datetime import timedelta
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..models.alert import Alert
from ..models.commit import Commit
from ..models.merge_request import MergeRequest, MergeRequestStatus
from ..models.project import Project
from ..models.user import User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/{project_id}/overview")
def get_overview(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    merge_requests = db.query(MergeRequest).filter(MergeRequest.project_id == project_id).all()
    open_count = sum(1 for mr in merge_requests if mr.status == MergeRequestStatus.OPEN)

    mr_ids = [mr.id for mr in merge_requests]
    commit_count = (
        db.query(Commit).filter(Commit.merge_request_id.in_(mr_ids)).count()
        if mr_ids else 0
    )

    unresolved_alerts = (
        db.query(Alert)
        .filter(Alert.project_id == project_id, Alert.is_resolved == False)
        .count()
    )

    contributor_ids = {mr.author_id for mr in merge_requests if mr.author_id}

    # Project score: arithmetic mean of MR scores, on the same 0..1000 scale.
    # Also expose per-MR contributions and min/max so the UI can explain
    # exactly where the number comes from.
    scored_mrs = [mr for mr in merge_requests if mr.score is not None]
    if scored_mrs:
        scores = [mr.score or 0.0 for mr in scored_mrs]
        project_score = round(sum(scores) / len(scores), 2)
        score_min = round(min(scores), 2)
        score_max = round(max(scores), 2)
        # Lowest-scoring MRs are usually the most useful drill-down.
        ranked = sorted(scored_mrs, key=lambda m: m.score or 0.0)
        sample = []
        for m in ranked[:5]:
            sample.append({
                "id": str(m.id),
                "title": m.title,
                "score": round(m.score or 0.0, 2),
                "lines_modified": m.lines_modified or 0,
                "jira_linked": bool(m.jira_task_id),
            })
    else:
        project_score = 0.0
        score_min = 0.0
        score_max = 0.0
        sample = []

    jira_linked_count = sum(1 for mr in merge_requests if mr.jira_task_id)

    return {
        "project_id": str(project_id),
        "project_name": project.name,
        "total_merge_requests": len(merge_requests),
        "open_merge_requests": open_count,
        "total_commits": commit_count,
        "unresolved_alerts": unresolved_alerts,
        "total_contributors": len(contributor_ids),
        "project_score": project_score,
        "score_breakdown": {
            "scored_mr_count": len(scored_mrs),
            "min_mr_score": score_min,
            "max_mr_score": score_max,
            "jira_linked_count": jira_linked_count,
            "lowest_mrs": sample,
        },
    }


@router.get("/{project_id}/scores")
def get_scores(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    merge_requests = db.query(MergeRequest).filter(MergeRequest.project_id == project_id).all()

    buckets: Dict[str, Dict[str, Any]] = {}
    for mr in merge_requests:
        if not mr.author_id:
            continue
        b = buckets.setdefault(mr.author_id, {
            "user_id": str(mr.author_id),
            "name": "Unknown",
            "email": "",
            "_scores": [],
            "merge_request_count": 0,
        })
        b["_scores"].append(mr.score or 0.0)
        b["merge_request_count"] += 1

    if buckets:
        users = db.query(User).filter(User.id.in_(list(buckets.keys()))).all()
        for u in users:
            if u.id in buckets:
                buckets[u.id]["name"] = u.name
                buckets[u.id]["email"] = u.email

    out: List[Dict[str, Any]] = []
    for b in buckets.values():
        scores = b.pop("_scores")
        total = round(sum(scores), 2) if scores else 0.0
        b["total_score"] = total  # NOTE: now SUM of MR scores (0..1000)
        b["min_score"] = round(min(scores), 2) if scores else 0.0
        b["max_score"] = round(max(scores), 2) if scores else 0.0
        out.append(b)

    return sorted(out, key=lambda x: x["total_score"], reverse=True)


@router.get("/{project_id}/timeline")
def get_timeline(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    merge_requests = db.query(MergeRequest).filter(MergeRequest.project_id == project_id).all()

    weeks: Dict[str, Dict[str, Any]] = {}
    for mr in merge_requests:
        day = mr.created_at.date()
        week_start = (day - timedelta(days=day.weekday())).isoformat()

        if week_start not in weeks:
            weeks[week_start] = {
                "week": week_start,
                "total_score": 0.0,
                "merge_request_count": 0,
            }
        weeks[week_start]["total_score"] += mr.score or 0.0
        weeks[week_start]["merge_request_count"] += 1

    return sorted(weeks.values(), key=lambda x: x["week"])
