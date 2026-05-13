from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..models.user import User
from ..models.alert import Alert
from ..schemas.alert import AlertResponse

router = APIRouter(prefix="/alerts", tags=["alerts"])


# FIX 8: global alerts endpoint across all projects
@router.get("", response_model=List[AlertResponse])
def get_all_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Alert).order_by(Alert.created_at.desc()).all()


@router.post("/{alert_id}/resolve", response_model=AlertResponse)
def resolve_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    alert.is_resolved = True
    alert.resolved_at = datetime.utcnow()
    alert.resolved_by = getattr(current_user, "name", None) or getattr(current_user, "email", None)
    db.commit()
    db.refresh(alert)
    return alert
