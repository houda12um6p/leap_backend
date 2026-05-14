from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..models.user import User
from ..services.score_engine import (
    calculate_developer_score,
    calculate_mr_score,
    calculate_project_score,
)

router = APIRouter(prefix="/scores", tags=["scores"])


@router.post("/mr/{mr_id}/calculate")
def score_merge_request(
    mr_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    score = calculate_mr_score(mr_id, db)
    return {"mr_id": str(mr_id), "score": score}


@router.post("/developer/{user_id}/calculate")
def score_developer(
    user_id: str,
    project_id: str | None = None,  # optional — needed for alert creation
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    total = calculate_developer_score(user_id, db, project_id=project_id)
    return {"user_id": str(user_id), "total_score": total}


@router.post("/project/{project_id}/calculate")
def score_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    project_total = calculate_project_score(project_id, db)
    return {"project_id": str(project_id), "project_total_score": project_total}
