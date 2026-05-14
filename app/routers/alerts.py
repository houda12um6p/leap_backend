from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..models.alert import Alert
from ..models.user import User
from ..schemas.alert import AlertResponse

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertResponse])
def get_all_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Alert]:
    return db.query(Alert).order_by(Alert.created_at.desc()).all()


@router.post("/{alert_id}/resolve", response_model=AlertResponse)
def resolve_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Alert:
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    alert.is_resolved = True
    alert.resolved_at = datetime.now(UTC)
    alert.resolved_by = getattr(current_user, "name", None) or getattr(current_user, "email", None)
    db.commit()
    db.refresh(alert)
    return alert
