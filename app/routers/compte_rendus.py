import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..models.compte_rendu import CompteRendu
from ..models.user import User
from ..services.compte_rendu_service import analyze_compte_rendu
from ..services.file_extractor import extract_text

router = APIRouter(prefix="/projects", tags=["compte_rendus"])


class CompteRenduCreate(BaseModel):
    raw_text: str


def serialize_cr(cr: CompteRendu) -> dict[str, Any]:
    now = datetime.now(UTC)
    expires_at = cr.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
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


async def _build_and_save_cr(project_id: str, raw_text: str, db: Session) -> CompteRendu:
    result = await analyze_compte_rendu(raw_text)
    cr = CompteRendu(
        project_id=project_id,
        raw_text=raw_text,
        language=result.get("language", "fr"),
        decisions=json.dumps(result.get("decisions", []), ensure_ascii=False),
        actions=json.dumps(result.get("actions", []), ensure_ascii=False),
        blocages=json.dumps(result.get("blocages", []), ensure_ascii=False),
        resume=result.get("resume", ""),
    )
    db.add(cr)
    db.commit()
    db.refresh(cr)
    return cr


@router.post("/{project_id}/compte-rendus", status_code=201)
async def create_compte_rendu(
    project_id: str,
    body: CompteRenduCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    cr = await _build_and_save_cr(project_id, body.raw_text, db)
    return serialize_cr(cr)


@router.post("/{project_id}/compte-rendus/upload", status_code=201)
async def create_compte_rendu_from_file(
    project_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    allowed = {".pdf", ".docx", ".doc", ".txt"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file type '{ext}'. Allowed: pdf, docx, doc, txt"
        )

    file_bytes = await file.read()
    if len(file_bytes) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File too large. Maximum size is 10MB."
        )

    try:
        raw_text = extract_text(file.filename, file_bytes)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not read file: {str(e)}"
        ) from e

    if len(raw_text.strip()) < 30:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Extracted text is too short. Is the file empty or scanned without OCR?"
        )

    cr = await _build_and_save_cr(project_id, raw_text, db)
    return serialize_cr(cr)


@router.get("/{project_id}/compte-rendus")
def get_compte_rendus(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    crs = db.query(CompteRendu).filter(
        CompteRendu.project_id == project_id
    ).order_by(CompteRendu.created_at.desc()).all()
    return [serialize_cr(cr) for cr in crs]


@router.get("/{project_id}/compte-rendus/active")
def get_active_compte_rendus(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    crs = db.query(CompteRendu).filter(
        CompteRendu.project_id == project_id,
        CompteRendu.expires_at > now
    ).order_by(CompteRendu.created_at.desc()).all()
    return [serialize_cr(cr) for cr in crs]
