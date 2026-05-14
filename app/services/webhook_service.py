import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from ..models.jira_task import JiraTask
from ..models.merge_request import MergeRequest
from ..models.project import Project
from ..models.review_comment import ReviewComment
from ..services.github_service import GitHubService
from ..services.jira_service import JiraService
from ..services.llm_service import classify_comment


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    s = value
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _parse_repo_url(url: str) -> tuple[str, str] | None:
    if not url:
        return None
    cleaned = url.strip().rstrip("/")
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]
    m = re.search(r"[/:]([^/:]+)/([^/]+)$", cleaned)
    if not m:
        return None
    return m.group(1), m.group(2)


def _find_project_by_repo(db: Session, repo_full_name: str) -> Project | None:
    if not repo_full_name:
        return None
    needle = repo_full_name.lower()
    # NOTE: full table scan — acceptable for small project count.
    # For production scale, add an index on Project.repo_url.
    for p in db.query(Project).all():
        if needle in (p.repo_url or "").lower():
            return p
    return None


class WebhookService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.jira_service = JiraService(db)
        self.github_service = GitHubService(db)

    async def handle_github_push(self, payload: dict[str, Any]) -> dict[str, Any]:
        repo_full_name = payload.get("repository", {}).get("full_name", "")
        project = _find_project_by_repo(self.db, repo_full_name)
        if project is None:
            return {"status": "ignored", "reason": "no matching project", "repo": repo_full_name}

        owner_repo = _parse_repo_url(project.repo_url) or _parse_repo_url(repo_full_name)
        if owner_repo is None:
            return {"status": "ignored", "reason": "unparsable repo url"}

        before = self.db.query(MergeRequest).filter(MergeRequest.project_id == project.id).count()
        synced = await self.github_service.sync_pull_requests(owner_repo[0], owner_repo[1], project.id)
        after = self.db.query(MergeRequest).filter(MergeRequest.project_id == project.id).count()

        return {
            "status": "success",
            "repo": repo_full_name,
            "project_id": project.id,
            "merge_requests_synced": len(synced),
            "merge_requests_added": max(0, after - before),
            "commits_processed": sum(len(c.commits) for c in synced),
        }

    async def handle_github_pull_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        action = payload.get("action")
        if action not in ("opened", "synchronize", "reopened", "closed", "edited"):
            return {"status": "ignored", "action": action}

        repo_full_name = payload.get("repository", {}).get("full_name", "")
        project = _find_project_by_repo(self.db, repo_full_name)
        if project is None:
            return {"status": "ignored", "action": action, "reason": "no matching project"}

        owner_repo = _parse_repo_url(project.repo_url) or _parse_repo_url(repo_full_name)
        if owner_repo is None:
            return {"status": "ignored", "action": action, "reason": "unparsable repo url"}

        pr_data = payload.get("pull_request", {}) or {}
        pr_number = pr_data.get("number")
        if pr_number is None:
            return {"status": "ignored", "action": action, "reason": "missing pull_request.number"}

        mr = await self.github_service.sync_one_pull_request(
            owner_repo[0], owner_repo[1], project.id, int(pr_number)
        )

        return {
            "status": "success",
            "action": action,
            "pr_id": mr.github_id,
            "title": mr.title,
            "mr_id": mr.id,
            "jira_task_id": mr.jira_task_id,
        }

    async def handle_github_review_comment(self, payload: dict[str, Any]) -> dict[str, Any]:
        action = payload.get("action", "")
        if action not in ("created", "edited", "deleted"):
            return {"status": "ignored", "action": action}

        comment_data = payload.get("comment", {}) or {}
        pr_data = payload.get("pull_request", {}) or {}
        comment_id = comment_data.get("id")
        body = (comment_data.get("body") or "").strip()
        github_pr_number = pr_data.get("number")

        mr = (
            self.db.query(MergeRequest)
            .filter(MergeRequest.github_id == github_pr_number)
            .first()
        )
        if not mr:
            return {"status": "ignored", "action": action, "reason": "unknown PR"}

        existing = (
            self.db.query(ReviewComment)
            .filter(
                ReviewComment.merge_request_id == mr.id,
                ReviewComment.body == body,
            )
            .first()
            if body
            else None
        )

        if action == "deleted":
            if existing:
                self.db.delete(existing)
                self.db.commit()
            return {
                "status": "success",
                "action": action,
                "pr_id": github_pr_number,
                "comment_id": comment_id,
                "severity_weight": 0,
            }

        weight = await classify_comment(body) if body else 0

        if existing:
            existing.severity_weight = weight
            self.db.commit()
            stored_id = existing.id
        else:
            rc = ReviewComment(
                body=body,
                severity_weight=weight,
                merge_request_id=mr.id,
            )
            self.db.add(rc)
            self.db.commit()
            stored_id = rc.id

        return {
            "status": "success",
            "action": action,
            "pr_id": github_pr_number,
            "comment_id": str(stored_id),
            "severity_weight": weight,
        }

    async def handle_jira_issue_updated(self, payload: dict[str, Any]) -> dict[str, Any]:
        event = payload.get("webhookEvent", "") or ""
        issue = payload.get("issue", {}) or {}
        jira_key = issue.get("key")
        if not jira_key:
            return {"status": "ignored", "reason": "missing issue.key"}

        fields = issue.get("fields", {}) or {}
        summary = fields.get("summary") or ""
        status_obj = fields.get("status") or {}
        new_status = status_obj.get("name") or ""
        story_points_raw = (
            fields.get("customfield_10016")
            if fields.get("customfield_10016") is not None
            else fields.get("story_points")
        )
        story_points = int(story_points_raw) if story_points_raw is not None else 0

        jira_task = self.jira_service.find_jira_task_by_key(jira_key)

        if event == "jira:issue_deleted":
            if jira_task:
                self.db.delete(jira_task)
                self.db.commit()
                return {"status": "success", "action": "deleted", "jira_key": jira_key}
            return {"status": "ignored", "action": "deleted", "reason": "unknown task"}

        if jira_task:
            jira_task.summary = summary
            jira_task.status = new_status
            if story_points:
                jira_task.story_points = story_points
            jira_task.updated_at = datetime.now(UTC)
            self.db.commit()
            return {
                "status": "success",
                "action": "updated",
                "jira_key": jira_key,
                "new_status": new_status,
            }

        new_task = JiraTask(
            jira_key=jira_key,
            summary=summary,
            status=new_status,
            story_points=story_points,
            project_id=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.db.add(new_task)
        self.db.commit()
        return {
            "status": "success",
            "action": "created",
            "jira_key": jira_key,
            "task_id": str(new_task.id),
            "project_id": None,
        }
