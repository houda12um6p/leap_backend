import hashlib
import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.database import get_db
from ..services.webhook_service import WebhookService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class WebhookResponse(BaseModel):
    status: str
    message: str = ""


async def verify_github_signature(
    request: Request,
    x_hub_signature_256: str = Header(None),
):
    secret = settings.github_webhook_secret
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GITHUB_WEBHOOK_SECRET is not configured. "
                   "Set it in .env before using webhooks.",
        )
    if not x_hub_signature_256:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing X-Hub-Signature-256 header",
        )
    body = await request.body()
    expected = "sha256=" + hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, x_hub_signature_256):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid webhook signature",
        )


@router.post("/github/push", response_model=WebhookResponse)
async def github_push_webhook(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(verify_github_signature),
):
    payload = await request.json()
    service = WebhookService(db)
    result = await service.handle_github_push(payload)
    if result["status"] == "success":
        return WebhookResponse(
            status="success",
            message=f"prs_synced={result.get('merge_requests_synced', 0)} commits_processed={result.get('commits_processed', 0)}",
        )
    if result["status"] == "ignored":
        return WebhookResponse(status="ignored", message=result.get("reason", ""))
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=result.get("message", "Unknown error"),
    )


@router.post("/github/pull-request", response_model=WebhookResponse)
async def github_pull_request_webhook(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(verify_github_signature),
):
    payload = await request.json()
    service = WebhookService(db)
    result = await service.handle_github_pull_request(payload)
    if result["status"] == "success":
        return WebhookResponse(
            status="success",
            message=f"action={result.get('action')} pr={result.get('pr_id')} mr_id={result.get('mr_id')}",
        )
    if result["status"] == "ignored":
        return WebhookResponse(
            status="ignored",
            message=f"action={result.get('action')} reason={result.get('reason', '')}",
        )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=result.get("message", "Unknown error"),
    )


@router.post("/github/review-comment", response_model=WebhookResponse)
async def github_review_comment_webhook(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(verify_github_signature),
):
    payload = await request.json()
    service = WebhookService(db)
    result = await service.handle_github_review_comment(payload)
    if result["status"] == "success":
        return WebhookResponse(
            status="processed",
            message=f"action={result.get('action')} severity_weight={result.get('severity_weight')} comment_id={result.get('comment_id')}",
        )
    if result["status"] == "ignored":
        return WebhookResponse(
            status="ignored",
            message=f"action={result.get('action')} reason={result.get('reason', '')}",
        )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=result.get("message", "Unknown error"),
    )


@router.post("/jira/issue-updated", response_model=WebhookResponse)
async def jira_issue_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    service = WebhookService(db)
    result = await service.handle_jira_issue_updated(payload)
    if result["status"] == "success":
        return WebhookResponse(
            status="success",
            message=f"action={result.get('action')} key={result.get('jira_key')}",
        )
    if result["status"] == "ignored":
        return WebhookResponse(status="ignored", message=result.get("reason", ""))
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=result.get("message", "Unknown error"),
    )
