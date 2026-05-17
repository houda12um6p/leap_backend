from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.crypto import try_decrypt
from ..models.jira_task import JiraTask
from ..models.merge_request import MergeRequest
from ..models.project import Project


@dataclass(frozen=True)
class JiraCredentials:
    base_url: str
    email: str
    api_token: str
    project_key: str | None = None

    def auth(self) -> tuple[str, str]:
        return (self.email, self.api_token)

    def stripped_base_url(self) -> str:
        return self.base_url.rstrip('/')


def _parse_dt(s: str) -> datetime:
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _credentials_from_env() -> JiraCredentials | None:
    """Build credentials from settings if all three secrets are present."""
    if settings.jira_base_url and settings.jira_email and settings.jira_api_token:
        return JiraCredentials(
            base_url=settings.jira_base_url,
            email=settings.jira_email,
            api_token=settings.jira_api_token,
            project_key=settings.jira_project_key or None,
        )
    return None


def _credentials_from_project(project: Project) -> JiraCredentials | None:
    """Build credentials from a Project row if all three secrets are present."""
    token = try_decrypt(project.jira_api_token_encrypted)
    if project.jira_base_url and project.jira_email and token:
        return JiraCredentials(
            base_url=project.jira_base_url,
            email=project.jira_email,
            api_token=token,
            project_key=project.jira_key,
        )
    return None


def resolve_credentials(project: Project) -> JiraCredentials:
    """Per-project credentials win; otherwise fall back to env vars."""
    creds = _credentials_from_project(project) or _credentials_from_env()
    if not creds:
        missing = []
        if not project.jira_base_url and not settings.jira_base_url: missing.append("Jira base URL")
        if not project.jira_email    and not settings.jira_email:    missing.append("Jira email")
        if not try_decrypt(project.jira_api_token_encrypted) and not settings.jira_api_token:
            missing.append("Jira API token")
        raise RuntimeError(
            "Jira is not configured for this project. Missing: " + ", ".join(missing) +
            ". Open the project's Edit form to add credentials."
        )
    return creds


class JiraService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._sp_field: str | None = None

    def _detect_story_points_field(self, creds: JiraCredentials) -> str:
        try:
            resp = httpx.get(
                f"{creds.stripped_base_url()}/rest/api/3/field",
                auth=creds.auth(),
                timeout=10.0,
            )
            if resp.status_code != 200:
                return "customfield_10016"
            fields = resp.json()
            for field in fields:
                name = field.get("name", "").lower()
                if "story point" in name or name == "story points":
                    return field["id"]
            return "customfield_10016"
        except Exception:
            return "customfield_10016"

    def fetch_tasks(
        self,
        credentials: JiraCredentials,
        project_key: str | None = None,
    ) -> list[dict[str, Any]]:
        effective_key = (project_key or credentials.project_key or "").strip()
        if not effective_key:
            raise RuntimeError(
                "No Jira project key supplied. Set the project's jira_key field."
            )
        if self._sp_field is None:
            self._sp_field = self._detect_story_points_field(credentials)
        sp_field = self._sp_field
        url = f"{credentials.stripped_base_url()}/rest/api/3/search/jql"
        payload = {
            "jql": f"project={effective_key} ORDER BY created DESC",
            "maxResults": 50,
            "fields": ["summary", "status", sp_field, "customfield_10016", "created", "updated"],
        }
        response = httpx.post(url, json=payload, auth=credentials.auth())
        response.raise_for_status()
        data = response.json()

        tasks = []
        for issue in data.get("issues", []):
            fields = issue.get("fields", {})
            story_points = (
                fields.get(sp_field) or
                fields.get("customfield_10016") or
                fields.get("story_points") or
                0
            )
            tasks.append({
                "jira_key": issue["key"],
                "summary": fields.get("summary", ""),
                "status": fields.get("status", {}).get("name", "unknown"),
                "story_points": int(story_points) if story_points else 0,
                "created_at": fields.get("created", ""),
                "updated_at": fields.get("updated", ""),
            })
        return tasks

    def fetch_sprints(
        self,
        credentials: JiraCredentials,
        project_key: str | None = None,
    ) -> list[dict[str, Any]]:
        key = (project_key or credentials.project_key or "").strip()
        if not key:
            raise RuntimeError("No Jira project key supplied for sprints.")
        url = f"{credentials.stripped_base_url()}/rest/agile/1.0/board"
        params = {"projectKeyOrId": key}
        response = httpx.get(url, params=params, auth=credentials.auth())
        response.raise_for_status()
        boards = response.json().get("values", [])
        if not boards:
            return []

        board_id = boards[0]["id"]
        sprint_url = f"{credentials.stripped_base_url()}/rest/agile/1.0/board/{board_id}/sprint"
        sprint_response = httpx.get(sprint_url, auth=credentials.auth())
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

    def sync_tasks(self, project_id: str) -> list[JiraTask]:
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise RuntimeError(f"Project {project_id} not found")
        credentials = resolve_credentials(project)
        tasks = self.fetch_tasks(credentials, project_key=project.jira_key)
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
                    created_at=_parse_dt(task_data["created_at"]) if task_data["created_at"] else datetime.now(UTC),
                    updated_at=_parse_dt(task_data["updated_at"]) if task_data["updated_at"] else datetime.now(UTC),
                )
                self.db.add(new_task)
                self.db.commit()
                synced.append(new_task)

        return synced

    def find_jira_task_by_key(self, jira_key: str) -> JiraTask | None:
        return self.db.query(JiraTask).filter(JiraTask.jira_key == jira_key).first()

    def link_merge_request_to_jira_task(self, mr_id: str, jira_key: str) -> MergeRequest | None:
        mr = self.db.query(MergeRequest).filter(MergeRequest.id == mr_id).first()
        task = self.find_jira_task_by_key(jira_key)
        if not mr or not task:
            return None
        mr.jira_task_id = task.id
        self.db.commit()
        return mr
