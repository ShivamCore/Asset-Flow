"""Idempotent seed for the foundation-owned ``assets`` table.

The frontend persists Assets/Departments/Employees/Categories in a browser store
(the production contract references them by string id only). The backend modules
resolve those ids through their ``AssetGateway`` against a real ``assets`` table.
To make Booking / Maintenance / Asset-Audit / Dashboard work end-to-end against
the *same* asset ids the UI shows, we seed this table to mirror the frontend's
local-store seed exactly (``AST-0001`` … ``AST-0016``, matching names / statuses
/ departments).

Only the documented contract columns are created here — ``id``, ``name``,
``status``, ``department_id`` — the same columns the gateways read. ``asset_tag``
carries the same value as ``id``: they are one identifier on the unified table.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

# (name, status, department_id) in frontend seed order → id = AST-000{n}
_ASSET_SEED = [
    ("MacBook Pro 16\"", "allocated", "DEP-ENG"),
    ("Dell Latitude 7440", "allocated", "DEP-OPS"),
    ("ThinkPad X1 Carbon", "available", "DEP-IT"),
    ("Dell UltraSharp U2723QE", "allocated", "DEP-ENG"),
    ("LG 27UP850", "available", "DEP-IT"),
    ("iPhone 15 Pro", "allocated", "DEP-MKT"),
    ("iPad Air", "reserved", "DEP-OPS"),
    ("Cisco Catalyst 9200", "available", "DEP-IT"),
    ("Ubiquiti UniFi AP", "under_maintenance", "DEP-IT"),
    ("Herman Miller Aeron", "allocated", "DEP-HR"),
    ("Standing Desk Pro", "available", "DEP-OPS"),
    ("Ford Transit Van", "allocated", "DEP-OPS"),
    ("Oscilloscope DSOX", "available", "DEP-ENG"),
    ("3D Printer Prusa", "under_maintenance", "DEP-ENG"),
    ("Surface Pro 9", "retired", None),
    ("Projector EB-2250U", "lost", "DEP-MKT"),
]


def ensure_assets_table(db: Session) -> None:
    """Create the shared ``assets`` contract table if it does not exist.

    The Asset module is external in the production contract, so no ORM model owns
    this table inside the backend. We create the minimal contract shape the
    gateways read against.
    """
    db.execute(
        text(
            "CREATE TABLE IF NOT EXISTS assets ("
            "id VARCHAR PRIMARY KEY, "
            "asset_tag VARCHAR, "
            "name VARCHAR NOT NULL, "
            "status VARCHAR NOT NULL, "
            "department_id VARCHAR"
            ")"
        )
    )


def seed_assets(db: Session) -> int:
    """Insert the demo asset estate if the table is empty. Returns rows added."""
    ensure_assets_table(db)
    existing = db.execute(text("SELECT COUNT(*) FROM assets")).scalar_one()
    if existing:
        return 0
    for i, (name, status, dept) in enumerate(_ASSET_SEED, start=1):
        db.execute(
            text(
                "INSERT INTO assets (id, asset_tag, name, status, department_id) "
                "VALUES (:id, :id, :name, :status, :dept)"
            ),
            {
                "id": f"AST-{i:04d}",
                "name": name,
                "status": status,
                "dept": dept,
            },
        )
    db.commit()
    return len(_ASSET_SEED)
