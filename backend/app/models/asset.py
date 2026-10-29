from sqlalchemy import Column, Integer, String, Boolean, Date, Float, Text, ForeignKey, JSON, text
from sqlalchemy.orm import relationship
from app.database import Base


class Asset(Base):
    __tablename__ = "assets"

    # String primary key ("AST-0001"): the contract the workflow modules read
    # through their AssetGateway, and the id the frontend store uses.
    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    asset_tag = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    serial_number = Column(String(100), unique=True, nullable=True, index=True)

    # Category linkage. Optional: assets seeded onto the shared contract exist
    # before the /api/v1 category taxonomy does.
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)

    # Status: available | allocated | reserved | under_maintenance | retired | lost
    # Lower-case snake_case, matching the AssetStatus vocabulary the modules use.
    status = Column(String(50), nullable=False, default="available",
                    server_default="available")

    # Owning department, part of the shared contract (read by the gateways).
    department_id = Column(String(50), nullable=True, index=True)

    # Financial
    purchase_date = Column(Date, nullable=True)
    purchase_cost = Column(Float, nullable=True)
    warranty_expiry = Column(Date, nullable=True)

    # Flags. The table is shared with the workflow modules, which write it with
    # SQLAlchemy Core rather than this model, so the defaults live in the schema
    # and not only in the ORM layer.
    is_bookable = Column(Boolean, default=False, nullable=False,
                         server_default=text("0"))
    is_active = Column(Boolean, default=True, nullable=False,
                       server_default=text("1"))

    # Dynamic category-specific JSON fields (e.g. RAM, CPU for Laptops)
    category_data = Column(JSON, nullable=True)

    # Relationships
    category = relationship("Category")
    allocations = relationship("Allocation", back_populates="asset", cascade="all, delete-orphan")
    transfers = relationship("Transfer", back_populates="asset", cascade="all, delete-orphan")
    history = relationship("AssetHistory", back_populates="asset", cascade="all, delete-orphan")
