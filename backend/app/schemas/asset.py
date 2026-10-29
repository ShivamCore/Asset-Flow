from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import date, datetime


class AssetBase(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: Optional[str] = None
    serial_number: Optional[str] = None
    category_id: int
    status: str = "available"
    purchase_date: Optional[date] = None
    purchase_cost: Optional[float] = None
    warranty_expiry: Optional[date] = None
    is_bookable: bool = False
    category_data: Optional[dict] = None


class AssetCreate(AssetBase):
    asset_tag: Optional[str] = None  # Auto-generated if not provided


class AssetUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = None
    serial_number: Optional[str] = None
    status: Optional[str] = None
    purchase_date: Optional[date] = None
    purchase_cost: Optional[float] = None
    warranty_expiry: Optional[date] = None
    is_bookable: Optional[bool] = None
    is_active: Optional[bool] = None
    category_data: Optional[dict] = None


class AssetResponse(AssetBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    asset_tag: str
    is_active: bool


class AssetHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: str
    performed_by_id: int
    action: str
    action_detail: Optional[str] = None
    performed_at: datetime
