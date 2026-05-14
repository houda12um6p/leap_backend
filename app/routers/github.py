from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..models.user import User
from ..services.github_service import GitHubService

router = APIRouter(prefix="/github", tags=["github"])


class SyncRequest(BaseModel):
    repo_owner: str
    repo_name: str
    project_id: str


class BranchResponse(BaseModel):
    name: str
    commit: dict[str, Any]


@router.post("/sync/commits")
async def sync_commits(
    sync_request: SyncRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    service = GitHubService(db)
    try:
        commits = await service.sync_commits(
            sync_request.repo_owner,
            sync_request.repo_name,
            sync_request.project_id,
        )
        return {"message": f"Synced {len(commits)} commits", "commits_count": len(commits)}
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"GitHub API error: {e.response.status_code} for {e.request.url}"
        ) from e
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Could not reach GitHub: {str(e)}"
        ) from e


@router.post("/sync/pull-requests")
async def sync_pull_requests(
    sync_request: SyncRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    service = GitHubService(db)
    try:
        pull_requests = await service.sync_pull_requests(
            sync_request.repo_owner,
            sync_request.repo_name,
            sync_request.project_id,
        )
        return {"message": f"Synced {len(pull_requests)} pull requests", "prs_count": len(pull_requests)}
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"GitHub API error: {e.response.status_code} for {e.request.url}"
        ) from e
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Could not reach GitHub: {str(e)}"
        ) from e


@router.post("/sync/review-comments")
async def sync_review_comments(
    sync_request: SyncRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    service = GitHubService(db)
    try:
        result = await service.sync_review_comments(
            sync_request.repo_owner,
            sync_request.repo_name,
            sync_request.project_id,
        )
        return {"message": f"Synced {result['synced_count']} review comments", **result}
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"GitHub API error: {e.response.status_code} for {e.request.url}"
        ) from e
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Could not reach GitHub: {str(e)}"
        ) from e


@router.get("/branches", response_model=list[BranchResponse])
async def get_branches(
    repo_owner: str,
    repo_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[BranchResponse]:
    service = GitHubService(db)
    try:
        branches = await service.fetch_branches(repo_owner, repo_name)
        return [BranchResponse(**branch) for branch in branches]
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"GitHub API error: {e.response.status_code} for {e.request.url}"
        ) from e
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Could not reach GitHub: {str(e)}"
        ) from e
