"""AssetFlow application bootstrap (the shared foundation owner).

Mounts every self-contained module onto one FastAPI app over one database. Each
module exposes ``register_routes(app)`` and consumes the shared ``Base`` /
``get_db`` / auth seam from this foundation, so wiring is uniform and no module's
internals are touched here.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine, SessionLocal
from app import models
from app.routers import auth, test
from app.models.role import Role

Base.metadata.create_all(bind=engine)

from app.routers import auth, departments, categories, employees, assets, allocations, transfers

from app.database import Base, SessionLocal, engine

# Importing every module's models registers their tables on the shared metadata
# before ``create_all`` runs. Dashboard and Reports own no tables (pure readers).
import app.booking.models  # noqa: F401
import app.maintenance.models  # noqa: F401
import app.asset_audit.models  # noqa: F401
import app.notifications.models  # noqa: F401
import app.audit.models  # noqa: F401

from app.booking import register_routes as register_booking
from app.maintenance import register_routes as register_maintenance
from app.asset_audit import register_routes as register_asset_audit
from app.notifications import register_routes as register_notifications
from app.audit import register_routes as register_audit
from app.dashboard import register_routes as register_dashboard
from app.reports import register_routes as register_reports
from app.seed import seed_assets


def _init_db() -> None:
    """Create all module tables + the shared ``assets`` contract, then seed."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_assets(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _init_db()
    yield


app = FastAPI(
    title="AssetFlow API",
    description="Enterprise Asset & Resource Management System",
    version="1.0.0",
    lifespan=lifespan,
)


def seed_database():
    db = SessionLocal()
    try:
        # Seed Roles
        roles_to_create = ["Admin", "Asset Manager", "Department Head", "Employee"]
        for role_name in roles_to_create:
            role = db.query(Role).filter(Role.name == role_name).first()
            if not role:
                role = Role(name=role_name)
                db.add(role)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
    finally:
        db.close()


@app.on_event("startup")
def startup_event():
    seed_database()


app.include_router(auth.router)
app.include_router(test.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for hackathon dev simplicity
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(departments.router, prefix="/api/v1")
app.include_router(categories.router, prefix="/api/v1")
app.include_router(employees.router, prefix="/api/v1")
app.include_router(assets.router, prefix="/api/v1")
app.include_router(allocations.router, prefix="/api/v1")
app.include_router(transfers.router, prefix="/api/v1")

# --- Mount every module (order is irrelevant; prefixes never collide) ---------
register_booking(app)
register_maintenance(app)
register_asset_audit(app)
register_notifications(app)
register_audit(app)
register_dashboard(app)
register_reports(app)


@app.get("/")
def root():
    return {
        "message": "Welcome to AssetFlow API",
        "status": "running",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}
