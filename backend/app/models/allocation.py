from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Allocation(Base):
    __tablename__ = "allocations"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(String(50), ForeignKey("assets.id"), nullable=False, index=True)

    # Recipient: either employee OR department (mutually exclusive)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)

    # Who performed the allocation
    allocated_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Timestamps
    allocated_at = Column(DateTime, nullable=False)
    expected_return_date = Column(DateTime, nullable=True)
    returned_at = Column(DateTime, nullable=True)

    # Condition notes
    condition_out = Column(Text, nullable=True)   # Condition when checked out
    condition_in = Column(Text, nullable=True)    # Condition when returned

    # Status: active | returned | overdue | transferred
    status = Column(String(50), nullable=False, default="active")

    # Relationships
    asset = relationship("Asset", back_populates="allocations")
    employee = relationship("Employee", foreign_keys=[employee_id])
    allocated_by = relationship("User", foreign_keys=[allocated_by_id])
