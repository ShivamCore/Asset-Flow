from pydantic import BaseModel, ConfigDict, model_validator
from typing import Optional
from datetime import datetime


class AllocationCreate(BaseModel):
    asset_id: str
    employee_id: Optional[int] = None
    department_id: Optional[int] = None
    expected_return_date: Optional[datetime] = None
    condition_out: Optional[str] = None

    @model_validator(mode="after")
    def validate_recipient(self) -> "AllocationCreate":
        if self.employee_id is None and self.department_id is None:
            raise ValueError("Either employee_id or department_id must be provided.")
        if self.employee_id is not None and self.department_id is not None:
            raise ValueError("Provide either employee_id or department_id, not both.")
        return self


class AllocationReturn(BaseModel):
    condition_in: Optional[str] = None


class AllocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: str
    employee_id: Optional[int] = None
    department_id: Optional[int] = None
    allocated_by_id: int
    allocated_at: datetime
    expected_return_date: Optional[datetime] = None
    returned_at: Optional[datetime] = None
    condition_out: Optional[str] = None
    condition_in: Optional[str] = None
    status: str
