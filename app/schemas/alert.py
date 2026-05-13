from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional

class AlertBase(BaseModel):
    type: str
    severity: str
    message: str
    is_resolved: bool = False
class AlertCreate(AlertBase):
    project_id: str


class AlertUpdate(BaseModel):
    type: Optional[str] = None
    severity: Optional[str] = None
    message: Optional[str] = None
    is_resolved: Optional[bool] = None


class AlertResponse(AlertBase):
    id: str
    project_id: str
    created_at: datetime
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
