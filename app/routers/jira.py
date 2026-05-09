from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..models.jira_task import JiraTask
from ..services.jira_service import JiraService

router = APIRouter(prefix="/jira", tags=["jira"])


class SyncRequest(BaseModel):
    project_id: str


@router.get("/tasks/{project_id}")
def get_jira_tasks(project_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    tasks = db.query(JiraTask).filter(JiraTask.project_id == project_id).all()
    return [
        {
            "jira_key": t.jira_key,
            "summary": t.summary,
            "status": t.status,
            "story_points": t.story_points,
        }
        for t in tasks
    ]


@router.post("/sync/tasks")
def sync_jira_tasks(req: SyncRequest, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    service = JiraService(db)
    synced = service.sync_tasks(req.project_id)
    return {
        "status": "success",
        "synced_count": len(synced),
        "tasks": [
            {
                "jira_key": t.jira_key,
                "summary": t.summary,
                "status": t.status,
                "story_points": t.story_points,
            }
            for t in synced
        ],
    }


@router.get("/sprints")
def get_sprints(
    project_key: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = JiraService(db)
    sprints = service.fetch_sprints(project_key=project_key)
    return {"status": "success", "sprints": sprints}


@router.post("/link")
def link_mr_to_task(mr_id: str, jira_key: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    service = JiraService(db)
    mr = service.link_merge_request_to_jira_task(mr_id, jira_key)
    if not mr:
        raise HTTPException(status_code=404, detail="MergeRequest or JiraTask not found")
    return {"status": "success", "mr_id": mr_id, "jira_key": jira_key}
