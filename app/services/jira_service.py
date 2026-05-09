import httpx
from sqlalchemy.orm import Session
from ..core.config import settings
from ..models.jira_task import JiraTask
from ..models.merge_request import MergeRequest
from datetime import datetime

def _parse_dt(s: str):
    return datetime.fromisoformat(s.replace('Z', '+00:00')).replace(tzinfo=None)

def _get_auth():
    return (settings.jira_email, settings.jira_api_token)

def _get_base_url():
    return settings.jira_base_url.rstrip('/')

def _require_jira_settings():
    """Raise early with a clear message if Jira env vars are missing."""
    missing = [k for k, v in {
        "JIRA_BASE_URL":    settings.jira_base_url,
        "JIRA_EMAIL":       settings.jira_email,
        "JIRA_API_TOKEN":   settings.jira_api_token,
        "JIRA_PROJECT_KEY": settings.jira_project_key,
    }.items() if not v]
    if missing:
        raise RuntimeError(
            f"Jira is not configured. Missing env vars: {', '.join(missing)}"
        )

class JiraService:
    def __init__(self, db: Session):
        self.db = db

    def fetch_tasks(self):
        _require_jira_settings()
        url = f"{_get_base_url()}/rest/api/3/search/jql"
        payload = {
            "jql": f"project={settings.jira_project_key} ORDER BY created DESC",
            "maxResults": 50,
            "fields": ["summary", "status", "customfield_10016", "created", "updated"],
        }
        response = httpx.post(url, json=payload, auth=_get_auth())
        response.raise_for_status()
        data = response.json()

        tasks = []
        for issue in data.get("issues", []):
            fields = issue.get("fields", {})
            story_points = fields.get("customfield_10016") or fields.get("story_points") or 0
            tasks.append({
                "jira_key": issue["key"],
                "summary": fields.get("summary", ""),
                "status": fields.get("status", {}).get("name", "unknown"),
                "story_points": int(story_points) if story_points else 0,
                "created_at": fields.get("created", ""),
                "updated_at": fields.get("updated", ""),
            })
        return tasks

    def fetch_sprints(self, project_key: str = None):
        _require_jira_settings()
        key = project_key or settings.jira_project_key
        url = f"{_get_base_url()}/rest/agile/1.0/board"
        params = {"projectKeyOrId": key}
        response = httpx.get(url, params=params, auth=_get_auth())
        response.raise_for_status()
        boards = response.json().get("values", [])
        if not boards:
            return []

        board_id = boards[0]["id"]
        sprint_url = f"{_get_base_url()}/rest/agile/1.0/board/{board_id}/sprint"
        sprint_response = httpx.get(sprint_url, auth=_get_auth())
        sprint_response.raise_for_status()
        sprints = sprint_response.json().get("values", [])

        return [
            {
                "id": s["id"],
                "name": s["name"],
                "state": s["state"],
                "start_date": s.get("startDate", ""),
                "end_date": s.get("endDate", ""),
            }
            for s in sprints
        ]

    def sync_tasks(self, project_id: str):
        tasks = self.fetch_tasks()
        synced = []

        for task_data in tasks:
            existing = self.db.query(JiraTask).filter(
                JiraTask.jira_key == task_data["jira_key"]
            ).first()

            if existing:
                existing.summary = task_data["summary"]
                existing.status = task_data["status"]
                existing.story_points = task_data["story_points"]
                existing.project_id = project_id
                if task_data["updated_at"]:
                    existing.updated_at = _parse_dt(task_data["updated_at"])
                self.db.commit()
                synced.append(existing)
            else:
                new_task = JiraTask(
                    jira_key=task_data["jira_key"],
                    summary=task_data["summary"],
                    status=task_data["status"],
                    story_points=task_data["story_points"],
                    project_id=project_id,
                    created_at=_parse_dt(task_data["created_at"]) if task_data["created_at"] else datetime.utcnow(),
                    updated_at=_parse_dt(task_data["updated_at"]) if task_data["updated_at"] else datetime.utcnow(),
                )
                self.db.add(new_task)
                self.db.commit()
                synced.append(new_task)

        return synced

    def find_jira_task_by_key(self, jira_key: str):
        return self.db.query(JiraTask).filter(JiraTask.jira_key == jira_key).first()

    def link_merge_request_to_jira_task(self, mr_id: str, jira_key: str):
        mr = self.db.query(MergeRequest).filter(MergeRequest.id == mr_id).first()
        task = self.find_jira_task_by_key(jira_key)
        if not mr or not task:
            return None
        mr.jira_task_id = task.id
        self.db.commit()
        return mr
