from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.allocation import Allocation
from app.models.asset import Asset
from app.models.asset_history import AssetHistory
from app.models.employee import Employee
from app.models.user import User
from app.routers.deps import get_current_user, RoleChecker
from app.schemas.allocation import AllocationCreate, AllocationReturn, AllocationResponse

router = APIRouter(prefix="/allocations", tags=["Allocations"])

manager_or_above = RoleChecker(["Admin", "Asset Manager"])


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
# GET /allocations/  – List allocations (filterable by status)
# ──────────────────────────────────────────────────────────────────────────────
@router.get("/", response_model=List[AllocationResponse])
def list_allocations(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status: active | returned | overdue | transferred"),
    asset_id: Optional[int] = Query(None),
    employee_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = db.query(Allocation)
    if status_filter:
        query = query.filter(Allocation.status == status_filter)
    if asset_id:
        query = query.filter(Allocation.asset_id == asset_id)
    if employee_id:
        query = query.filter(Allocation.employee_id == employee_id)
    return query.order_by(Allocation.allocated_at.desc()).offset(skip).limit(limit).all()


# ──────────────────────────────────────────────────────────────────────────────
# GET /allocations/overdue  – List overdue (must come before /{id})
# ──────────────────────────────────────────────────────────────────────────────
@router.get("/overdue", response_model=List[AllocationResponse])
def list_overdue(
    db: Session = Depends(get_db),
    _: User = Depends(manager_or_above),
):
    now = datetime.now(timezone.utc)
    return (
        db.query(Allocation)
        .filter(
            Allocation.status == "active",
            Allocation.expected_return_date != None,
            Allocation.expected_return_date < now,
        )
        .all()
    )


# ──────────────────────────────────────────────────────────────────────────────
# GET /allocations/{id}  – Single allocation detail
# ──────────────────────────────────────────────────────────────────────────────
@router.get("/{allocation_id}", response_model=AllocationResponse)
def get_allocation(
    allocation_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    alloc = db.query(Allocation).filter(Allocation.id == allocation_id).first()
    if not alloc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allocation not found")
    return alloc


# ──────────────────────────────────────────────────────────────────────────────
# POST /allocations/  – Checkout an asset
# ──────────────────────────────────────────────────────────────────────────────
@router.post("/", response_model=AllocationResponse, status_code=status.HTTP_201_CREATED)
def checkout_asset(
    payload: AllocationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(manager_or_above),
):
    # Verify asset exists
    asset = db.query(Asset).filter(Asset.id == payload.asset_id, Asset.is_active == True).first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    # Conflict check: asset must be Available
    if asset.status != "available":
        active = (
            db.query(Allocation)
            .filter(Allocation.asset_id == asset.id, Allocation.status == "active")
            .first()
        )
        holder_info = ""
        if active:
            if active.employee_id:
                emp = db.query(Employee).filter(Employee.id == active.employee_id).first()
                holder_info = f"Currently held by: {emp.user.name} ({emp.employee_code})" if emp else ""
            elif active.department_id:
                holder_info = f"Currently allocated to department ID {active.department_id}"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Asset is not available (status: {asset.status}). {holder_info}".strip(),
        )

    # Validate recipient
    if payload.employee_id:
        emp = db.query(Employee).filter(Employee.id == payload.employee_id, Employee.is_active == True).first()
        if not emp:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found or inactive")

    now = datetime.now(timezone.utc)
    alloc = Allocation(
        asset_id=payload.asset_id,
        employee_id=payload.employee_id,
        department_id=payload.department_id,
        allocated_by_id=current_user.id,
        allocated_at=now,
        expected_return_date=payload.expected_return_date,
        condition_out=payload.condition_out,
        status="active",
    )
    db.add(alloc)

    asset.status = "allocated"
    _log(db, asset.id, current_user.id, "allocated",
         f"Checked out to {'employee ' + str(payload.employee_id) if payload.employee_id else 'department ' + str(payload.department_id)}")
    db.commit()
    db.refresh(alloc)
    return alloc


# ──────────────────────────────────────────────────────────────────────────────
# POST /allocations/{id}/return  – Return an asset
# ──────────────────────────────────────────────────────────────────────────────
@router.post("/{allocation_id}/return", response_model=AllocationResponse)
def return_asset(
    allocation_id: int,
    payload: AllocationReturn,
    db: Session = Depends(get_db),
    current_user: User = Depends(manager_or_above),
):
    alloc = db.query(Allocation).filter(Allocation.id == allocation_id).first()
    if not alloc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allocation not found")
    if alloc.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Allocation is already closed (status: {alloc.status})",
        )

    now = datetime.now(timezone.utc)
    alloc.returned_at = now
    alloc.condition_in = payload.condition_in
    alloc.status = "returned"

    asset = alloc.asset
    asset.status = "available"

    _log(db, asset.id, current_user.id, "returned",
         f"Returned from {'employee ' + str(alloc.employee_id) if alloc.employee_id else 'department ' + str(alloc.department_id)}. Condition: {payload.condition_in or 'Not noted'}")
    db.commit()
    db.refresh(alloc)
    return alloc
