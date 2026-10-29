from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.allocation import Allocation
from app.models.asset import Asset
from app.models.asset_history import AssetHistory
from app.models.employee import Employee
from app.models.transfer import Transfer
from app.models.user import User
from app.routers.deps import get_current_user, get_current_employee, RoleChecker
from app.schemas.transfer import TransferCreate, TransferAction, TransferResponse

router = APIRouter(prefix="/transfers", tags=["Transfers"])

manager_or_above = RoleChecker(["Admin", "Asset Manager"])
dept_head_or_above = RoleChecker(["Admin", "Asset Manager", "Department Head"])


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
# GET /transfers/  – List transfer requests
# ──────────────────────────────────────────────────────────────────────────────
@router.get("/", response_model=List[TransferResponse])
def list_transfers(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter: pending | approved | rejected"),
    asset_id: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = db.query(Transfer)
    if status_filter:
        query = query.filter(Transfer.status == status_filter)
    if asset_id:
        query = query.filter(Transfer.asset_id == asset_id)
    return query.order_by(Transfer.requested_at.desc()).offset(skip).limit(limit).all()


# ──────────────────────────────────────────────────────────────────────────────
# GET /transfers/{id}  – Single transfer detail
# ──────────────────────────────────────────────────────────────────────────────
@router.get("/{transfer_id}", response_model=TransferResponse)
def get_transfer(
    transfer_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    t = db.query(Transfer).filter(Transfer.id == transfer_id).first()
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transfer request not found")
    return t


# ──────────────────────────────────────────────────────────────────────────────
# POST /transfers/  – Request a transfer
# ──────────────────────────────────────────────────────────────────────────────
@router.post("/", response_model=TransferResponse, status_code=status.HTTP_201_CREATED)
def request_transfer(
    payload: TransferCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Asset must exist
    asset = db.query(Asset).filter(Asset.id == payload.asset_id, Asset.is_active == True).first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    # Must have an active allocation to an employee
    active_alloc = (
        db.query(Allocation)
        .filter(Allocation.asset_id == asset.id, Allocation.status == "active")
        .first()
    )
    if not active_alloc or not active_alloc.employee_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Asset must be actively allocated to an employee before a transfer can be requested.",
        )

    # Validate target employee
    to_emp = db.query(Employee).filter(Employee.id == payload.to_employee_id, Employee.is_active == True).first()
    if not to_emp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target employee not found or inactive")

    # Cannot transfer to the same person
    if active_alloc.employee_id == payload.to_employee_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot transfer asset to the same employee who currently holds it",
        )

    # Only one pending transfer per asset at a time
    pending = (
        db.query(Transfer)
        .filter(Transfer.asset_id == asset.id, Transfer.status == "pending")
        .first()
    )
    if pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A pending transfer request already exists for this asset",
        )

    now = datetime.now(timezone.utc)
    transfer = Transfer(
        asset_id=payload.asset_id,
        from_employee_id=active_alloc.employee_id,
        to_employee_id=payload.to_employee_id,
        requested_by_id=current_user.id,
        requested_at=now,
        status="pending",
        requester_notes=payload.requester_notes,
    )
    db.add(transfer)
    _log(db, asset.id, current_user.id, "transfer_requested",
         f"Transfer requested from employee {active_alloc.employee_id} → employee {payload.to_employee_id}")
    db.commit()
    db.refresh(transfer)
    return transfer


# ──────────────────────────────────────────────────────────────────────────────
# POST /transfers/{id}/action  – Approve or Reject a transfer
# ──────────────────────────────────────────────────────────────────────────────
@router.post("/{transfer_id}/action", response_model=TransferResponse)
def action_transfer(
    transfer_id: int,
    payload: TransferAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(dept_head_or_above),
):
    transfer = db.query(Transfer).filter(Transfer.id == transfer_id).first()
    if not transfer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transfer request not found")

    if transfer.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transfer has already been actioned (status: {transfer.status})",
        )

    now = datetime.now(timezone.utc)
    transfer.status = payload.action
    transfer.actioned_by_id = current_user.id
    transfer.actioned_at = now
    transfer.approver_notes = payload.approver_notes

    asset = transfer.asset

    if payload.action == "approved":
        # 1. Close existing allocation
        active_alloc = (
            db.query(Allocation)
            .filter(Allocation.asset_id == asset.id, Allocation.status == "active")
            .first()
        )
        if active_alloc:
            active_alloc.returned_at = now
            active_alloc.condition_in = "Transferred to new holder"
            active_alloc.status = "transferred"

        # 2. Open new allocation for the recipient
        new_alloc = Allocation(
            asset_id=asset.id,
            employee_id=transfer.to_employee_id,
            allocated_by_id=current_user.id,
            allocated_at=now,
            expected_return_date=active_alloc.expected_return_date if active_alloc else None,
            condition_out="Received via approved transfer",
            status="active",
        )
        db.add(new_alloc)
        asset.status = "allocated"

        _log(db, asset.id, current_user.id, "transfer_approved",
             f"Transfer approved. Asset reallocated from employee {transfer.from_employee_id} → {transfer.to_employee_id}")
    else:
        _log(db, asset.id, current_user.id, "transfer_rejected",
             f"Transfer rejected. Reason: {payload.approver_notes or 'None provided'}")

    db.commit()
    db.refresh(transfer)
    return transfer
