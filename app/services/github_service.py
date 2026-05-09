import re
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.security import get_password_hash
from ..models.commit import Commit
from ..models.merge_request import MergeRequest, MergeRequestStatus
from ..models.review_comment import ReviewComment
from ..models.user import User, UserRole
from .llm_service import classify_many


class GitHubService:
    def __init__(self, db: Session):
        self.db = db
        self.api_url = settings.github_api_url

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        token = getattr(settings, "github_token", "") or ""
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _map_pr_status(self, state: str, merged_at: Optional[str]) -> MergeRequestStatus:
        if merged_at:
            return MergeRequestStatus.MERGED
        s = (state or "").lower()
        if s == "closed":
            return MergeRequestStatus.CLOSED
        return MergeRequestStatus.OPEN

    def _get_or_create_user(self, email: str, name: str) -> User:
        user = self.db.query(User).filter(User.email == email).first()
        if user:
            return user
        user = User(
            name=name or email,
            email=email,
            password_hash=get_password_hash(secrets.token_hex(32)),
            role=UserRole.DEVELOPER,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    @staticmethod
    def _parse_iso(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)

    @staticmethod
    def _next_url(link_header: Optional[str]) -> Optional[str]:
        if not link_header:
            return None
        for part in link_header.split(","):
            section = part.split(";")
            if len(section) < 2:
                continue
            url = section[0].strip().lstrip("<").rstrip(">")
            rel = section[1].strip()
            if rel == 'rel="next"':
                return url
        return None

    async def _get_all(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        next_url: Optional[str] = url
        next_params: Optional[Dict[str, Any]] = {**(params or {}), "per_page": 100}
        while next_url:
            resp = await client.get(next_url, headers=self._headers(), params=next_params)
            resp.raise_for_status()
            page = resp.json()
            if not isinstance(page, list):
                break
            items.extend(page)
            next_url = self._next_url(resp.headers.get("Link"))
            next_params = None
        return items

    async def fetch_branches(self, repo_owner: str, repo_name: str) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=30) as client:
            raw = await self._get_all(
                client,
                f"{self.api_url}/repos/{repo_owner}/{repo_name}/branches",
            )
            return [{"name": b["name"], "commit": b["commit"]} for b in raw]

    async def fetch_commits(self, repo_owner: str, repo_name: str) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=60) as client:
            raw = await self._get_all(
                client,
                f"{self.api_url}/repos/{repo_owner}/{repo_name}/commits",
                params={"per_page": 100},
            )
            return [
                {
                    "sha": c["sha"],
                    "message": (c["commit"]["message"] or "").split("\n")[0],
                    "author": {
                        "email": (c["commit"]["author"] or {}).get("email", ""),
                        "name": (c["commit"]["author"] or {}).get("name", ""),
                    },
                    "date": (c["commit"]["author"] or {}).get("date"),
                }
                for c in raw
            ]

    async def _enrich_pr(
        self,
        client: httpx.AsyncClient,
        repo_owner: str,
        repo_name: str,
        pr_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        number = pr_summary["number"]
        detail_resp = await client.get(
            f"{self.api_url}/repos/{repo_owner}/{repo_name}/pulls/{number}",
            headers=self._headers(),
        )
        pr_detail = detail_resp.json() if detail_resp.status_code == 200 else pr_summary

        commits_raw = await self._get_all(
            client,
            f"{self.api_url}/repos/{repo_owner}/{repo_name}/pulls/{number}/commits",
        )
        commits: List[Dict[str, Any]] = []
        for c in commits_raw:
            author_block = (c.get("commit") or {}).get("author") or {}
            commits.append({
                "sha": c["sha"],
                "message": ((c.get("commit") or {}).get("message") or "").split("\n")[0],
                "author_email": author_block.get("email") or "",
                "author_name":  author_block.get("name")  or "",
                "date": author_block.get("date"),
            })

        if commits and commits[0]["author_email"]:
            author_email = commits[0]["author_email"]
            author_name = commits[0]["author_name"] or author_email
        else:
            login = (pr_summary.get("user") or {}).get("login") or "unknown"
            author_email = f"{login}@github.local"
            author_name = login

        return {
            "id": number,
            "title": pr_summary["title"],
            "author": {"email": author_email, "name": author_name},
            "merged_at": pr_detail.get("merged_at"),
            "state": pr_detail.get("state") or pr_summary.get("state") or "open",
            "additions": pr_detail.get("additions", 0),
            "deletions": pr_detail.get("deletions", 0),
            "created_at": pr_summary["created_at"],
            "updated_at": pr_summary["updated_at"],
            "commits": commits,
        }

    async def fetch_pull_requests(self, repo_owner: str, repo_name: str) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=60) as client:
            summaries = await self._get_all(
                client,
                f"{self.api_url}/repos/{repo_owner}/{repo_name}/pulls",
                params={"state": "all"},
            )
            enriched: List[Dict[str, Any]] = []
            for pr in summaries:
                enriched.append(await self._enrich_pr(client, repo_owner, repo_name, pr))
            return enriched

    async def fetch_one_pull_request(
        self,
        repo_owner: str,
        repo_name: str,
        pr_number: int,
    ) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(
                f"{self.api_url}/repos/{repo_owner}/{repo_name}/pulls/{pr_number}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return await self._enrich_pr(client, repo_owner, repo_name, resp.json())

    def _upsert_pr(self, project_id: str, pr: Dict[str, Any]) -> MergeRequest:
        mr_author = self._get_or_create_user(pr["author"]["email"], pr["author"]["name"])
        mr_status = self._map_pr_status(pr["state"], pr.get("merged_at"))
        lines_modified = (pr.get("additions") or 0) + (pr.get("deletions") or 0)
        created_at = self._parse_iso(pr["created_at"])
        updated_at = self._parse_iso(pr["updated_at"])

        mr = self.db.query(MergeRequest).filter(
            MergeRequest.github_id == pr["id"],
            MergeRequest.project_id == project_id,
        ).first()
        if mr:
            mr.title = pr["title"]
            mr.status = mr_status
            mr.lines_modified = lines_modified
            mr.author_id = mr_author.id
            if updated_at:
                mr.updated_at = updated_at
        else:
            mr = MergeRequest(
                github_id=pr["id"],
                title=pr["title"],
                author_id=mr_author.id,
                project_id=project_id,
                status=mr_status,
                lines_modified=lines_modified,
                created_at=created_at,
                updated_at=updated_at,
            )
            self.db.add(mr)
            self.db.flush()

        for cd in pr["commits"]:
            if not cd["sha"]:
                continue
            if self.db.query(Commit).filter(Commit.sha == cd["sha"]).first():
                continue
            if not cd["author_email"]:
                continue
            commit_author = self._get_or_create_user(cd["author_email"], cd["author_name"])
            self.db.add(Commit(
                sha=cd["sha"],
                message=cd["message"],
                author_id=commit_author.id,
                merge_request_id=mr.id,
                date=self._parse_iso(cd["date"]) or datetime.now(timezone.utc),
            ))

        keys = re.findall(r"[A-Z]+-\d+", mr.title or "")
        if keys:
            from .jira_service import JiraService
            jira_service = JiraService(self.db)
            for key in keys:
                task = jira_service.find_jira_task_by_key(key)
                if task:
                    mr.jira_task_id = task.id
                    mr.story_points = task.story_points or 0
                    break

        return mr

    async def sync_pull_requests(
        self,
        repo_owner: str,
        repo_name: str,
        project_id: str,
    ) -> List[MergeRequest]:
        prs_data = await self.fetch_pull_requests(repo_owner, repo_name)
        synced: List[MergeRequest] = [self._upsert_pr(project_id, pr) for pr in prs_data]
        self.db.commit()
        return synced

    async def sync_one_pull_request(
        self,
        repo_owner: str,
        repo_name: str,
        project_id: str,
        pr_number: int,
    ) -> MergeRequest:
        pr = await self.fetch_one_pull_request(repo_owner, repo_name, pr_number)
        mr = self._upsert_pr(project_id, pr)
        self.db.commit()
        return mr

    async def sync_commits(
        self,
        repo_owner: str,
        repo_name: str,
        project_id: str,
    ) -> List[Commit]:
        await self.sync_pull_requests(repo_owner, repo_name, project_id)
        mr_ids = [
            mr.id for mr in self.db.query(MergeRequest)
            .filter(MergeRequest.project_id == project_id).all()
        ]
        if not mr_ids:
            return []
        return self.db.query(Commit).filter(Commit.merge_request_id.in_(mr_ids)).all()

    async def sync_review_comments(
        self,
        repo_owner: str,
        repo_name: str,
        project_id: str,
    ) -> dict:
        mrs = (
            self.db.query(MergeRequest)
            .filter(
                MergeRequest.project_id == project_id,
                MergeRequest.github_id.isnot(None),
            )
            .all()
        )

        pending: List[Dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=60) as client:
            for mr in mrs:
                comments_raw = await self._get_all(
                    client,
                    f"{self.api_url}/repos/{repo_owner}/{repo_name}/pulls/{mr.github_id}/comments",
                )
                for c in comments_raw:
                    body = (c.get("body") or "").strip()
                    if not body:
                        continue
                    already = (
                        self.db.query(ReviewComment)
                        .filter(
                            ReviewComment.merge_request_id == mr.id,
                            ReviewComment.body == body,
                        )
                        .first()
                    )
                    if already:
                        continue
                    pending.append({
                        "mr_id": mr.id,
                        "body": body,
                        "created_at": self._parse_iso(c.get("created_at")) or datetime.now(timezone.utc),
                    })

        weights = await classify_many([p["body"] for p in pending])
        for entry, weight in zip(pending, weights):
            self.db.add(ReviewComment(
                body=entry["body"],
                severity_weight=weight,
                merge_request_id=entry["mr_id"],
                created_at=entry["created_at"],
            ))
        self.db.commit()
        return {"synced_count": len(pending)}
