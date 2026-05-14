from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AlertBase(BaseModel):
    type: str
    severity: str
    message: str
    is_resolved: bool = False
class AlertCreate(AlertBase):
    project_id: str


class AlertUpdate(BaseModel):
    type: str | None = None
    severity: str | None = None
    message: str | None = None
    is_resolved: bool | None = None


class AlertResponse(AlertBase):
    id: str
    project_id: str
    created_at: datetime
    resolved_at: datetime | None = None
    resolved_by: str | None = None

    model_config = ConfigDict(from_attributes=True)
