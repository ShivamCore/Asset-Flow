from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Transfer(Base):
    __tablename__ = "transfers"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(String(50), ForeignKey("assets.id"), nullable=False, index=True)

    # From/To employees
    from_employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    to_employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)

    # Who submitted the transfer request
    requested_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # Who approved/rejected it
    actioned_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Timestamps
    requested_at = Column(DateTime, nullable=False)
    actioned_at = Column(DateTime, nullable=True)

    # Status: pending | approved | rejected
    status = Column(String(50), nullable=False, default="pending")

    # Notes from requester and approver
    requester_notes = Column(Text, nullable=True)
    approver_notes = Column(Text, nullable=True)

    # Relationships
    asset = relationship("Asset", back_populates="transfers")
    from_employee = relationship("Employee", foreign_keys=[from_employee_id])
    to_employee = relationship("Employee", foreign_keys=[to_employee_id])
    requested_by = relationship("User", foreign_keys=[requested_by_id])
    actioned_by = relationship("User", foreign_keys=[actioned_by_id])
