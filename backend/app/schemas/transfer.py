from pydantic import BaseModel, ConfigDict
from typing import Optional, Literal
from datetime import datetime


class TransferCreate(BaseModel):
    asset_id: str
    to_employee_id: int
    requester_notes: Optional[str] = None


class TransferAction(BaseModel):
    action: Literal["approved", "rejected"]
    approver_notes: Optional[str] = None


class TransferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: str
    from_employee_id: int
    to_employee_id: int
    requested_by_id: int
    actioned_by_id: Optional[int] = None
    requested_at: datetime
    actioned_at: Optional[datetime] = None
    status: str
    requester_notes: Optional[str] = None
    approver_notes: Optional[str] = None
