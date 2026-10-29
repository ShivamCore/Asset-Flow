import re
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.asset import Asset
from app.models.asset_history import AssetHistory
from app.models.user import User
from app.routers.deps import get_current_user, RoleChecker
from app.schemas.asset import AssetCreate, AssetUpdate, AssetResponse, AssetHistoryResponse

router = APIRouter(prefix="/assets", tags=["Assets"])

# Only Admins and Asset Managers can register/update assets
manager_or_above = RoleChecker(["Admin", "Asset Manager"])


def _generate_asset_tag(db: Session) -> str:
    """Auto-generate a unique asset tag in format AST-XXXX.

    Ids are strings on the shared contract, so the next number comes from the
    highest numeric suffix already in use rather than from an autoincrement.
    """
    highest = 0
    for (tag,) in db.query(Asset.asset_tag).all():
        match = re.fullmatch(r"AST-(\d+)", tag or "")
        if match:
            highest = max(highest, int(match.group(1)))
    return f"AST-{highest + 1:04d}"


def _log(db: Session, asset_id: str, user_id: int, action: str, detail: str = None):
    entry = AssetHistory(
        asset_id=asset_id,
        performed_by_id=user_id,
        action=action,
        action_detail=detail,
        performed_at=datetime.now(timezone.utc),
    )
    db.add(entry)


# ──────────────────────────────────────────────────────────────────────────────
# GET /assets/  – Directory with search & filters
# ──────────────────────────────────────────────────────────────────────────────
@router.get("/", response_model=List[AssetResponse])
def list_assets(
    q: Optional[str] = Query(None, description="Search by name, tag, or serial number"),
    category_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    is_bookable: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = db.query(Asset).filter(Asset.is_active == True)

    if q:
        like = f"%{q}%"
        query = query.filter(
            Asset.name.ilike(like)
            | Asset.asset_tag.ilike(like)
            | Asset.serial_number.ilike(like)
        )
    if category_id:
        query = query.filter(Asset.category_id == category_id)
    if status:
        query = query.filter(Asset.status == status)
    if is_bookable is not None:
        query = query.filter(Asset.is_bookable == is_bookable)

    return query.offset(skip).limit(limit).all()


# ──────────────────────────────────────────────────────────────────────────────
# GET /assets/{id}  – Get single asset detail
# ──────────────────────────────────────────────────────────────────────────────
@router.get("/{asset_id}", response_model=AssetResponse)
def get_asset(
    asset_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return asset


# ──────────────────────────────────────────────────────────────────────────────
# POST /assets/  – Register a new asset
# ──────────────────────────────────────────────────────────────────────────────
@router.post("/", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
def register_asset(
    payload: AssetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(manager_or_above),
):
    # Validate unique serial number
    if payload.serial_number:
        existing = db.query(Asset).filter(Asset.serial_number == payload.serial_number).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Serial number '{payload.serial_number}' is already registered (Asset: {existing.asset_tag})",
            )

    # Auto-generate tag if not provided
    tag = payload.asset_tag or _generate_asset_tag(db)

    # Verify tag uniqueness if provided manually
    if db.query(Asset).filter(Asset.asset_tag == tag).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Asset tag '{tag}' already exists",
        )

    asset = Asset(
        id=tag,
        name=payload.name,
        asset_tag=tag,
        description=payload.description,
        serial_number=payload.serial_number,
        category_id=payload.category_id,
        status=payload.status,
        purchase_date=payload.purchase_date,
        purchase_cost=payload.purchase_cost,
        warranty_expiry=payload.warranty_expiry,
        is_bookable=payload.is_bookable,
        is_active=True,
        category_data=payload.category_data,
    )
    db.add(asset)
    db.flush()

    _log(db, asset.id, current_user.id, "registered", f"Asset '{asset.name}' registered with tag {asset.asset_tag}")
    db.commit()
    db.refresh(asset)
    return asset


# ──────────────────────────────────────────────────────────────────────────────
# PUT /assets/{id}  – Update asset metadata
# ──────────────────────────────────────────────────────────────────────────────
@router.put("/{asset_id}", response_model=AssetResponse)
def update_asset(
    asset_id: str,
    payload: AssetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(manager_or_above),
):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    old_status = asset.status
    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(asset, field, value)

    if "status" in update_data and update_data["status"] != old_status:
        _log(db, asset.id, current_user.id, "status_changed",
             f"Status changed from '{old_status}' to '{update_data['status']}'")
    else:
        _log(db, asset.id, current_user.id, "updated", "Asset metadata updated")

    db.commit()
    db.refresh(asset)
    return asset


# ──────────────────────────────────────────────────────────────────────────────
# GET /assets/{id}/history  – Full audit trail
# ──────────────────────────────────────────────────────────────────────────────
@router.get("/{asset_id}/history", response_model=List[AssetHistoryResponse])
def get_asset_history(
    asset_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    return (
        db.query(AssetHistory)
        .filter(AssetHistory.asset_id == asset_id)
        .order_by(AssetHistory.performed_at.desc())
        .all()
    )
