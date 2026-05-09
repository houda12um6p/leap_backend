from datetime import datetime, timezone
import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..models.compte_rendu import CompteRendu
from ..models.user import User
from ..services.compte_rendu_service import analyze_compte_rendu
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/projects", tags=["compte_rendus"])

class CompteRenduCreate(BaseModel):
    raw_text: str

def serialize_cr(cr: CompteRendu) -> dict:
    now = datetime.now(timezone.utc)
    expires_at = cr.expires_at
    if expires_at.tzinfo is None:
        from datetime import timezone as tz
        expires_at = expires_at.replace(tzinfo=tz.utc)
    return {
        "id": cr.id,
        "project_id": cr.project_id,
        "raw_text": cr.raw_text,
        "language": cr.language,
        "decisions": json.loads(cr.decisions or "[]"),
        "actions": json.loads(cr.actions or "[]"),
        "blocages": json.loads(cr.blocages or "[]"),
        "resume": cr.resume,
        "created_at": cr.created_at.isoformat(),
        "expires_at": cr.expires_at.isoformat(),
        "is_active": now < expires_at,
        "days_remaining": max(0, (expires_at - now).days)
    }

@router.post("/{project_id}/compte-rendus", status_code=201)
async def create_compte_rendu(
    project_id: str,
    body: CompteRenduCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await analyze_compte_rendu(body.raw_text)
    cr = CompteRendu(
        project_id=project_id,
        raw_text=body.raw_text,
        language=result.get("language", "fr"),
        decisions=json.dumps(result.get("decisions", []), ensure_ascii=False),
        actions=json.dumps(result.get("actions", []), ensure_ascii=False),
        blocages=json.dumps(result.get("blocages", []), ensure_ascii=False),
        resume=result.get("resume", ""),
    )
    db.add(cr)
    db.commit()
    db.refresh(cr)
    return serialize_cr(cr)

@router.get("/{project_id}/compte-rendus")
def get_compte_rendus(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    crs = db.query(CompteRendu).filter(
        CompteRendu.project_id == project_id
    ).order_by(CompteRendu.created_at.desc()).all()
    return [serialize_cr(cr) for cr in crs]

@router.get("/{project_id}/compte-rendus/active")
def get_active_compte_rendus(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    now = datetime.now(timezone.utc)
    crs = db.query(CompteRendu).filter(
        CompteRendu.project_id == project_id,
        CompteRendu.expires_at > now
    ).order_by(CompteRendu.created_at.desc()).all()
    return [serialize_cr(cr) for cr in crs]
