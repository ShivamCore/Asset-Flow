from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base


class AssetHistory(Base):
    __tablename__ = "asset_history"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(String(50), ForeignKey("assets.id"), nullable=False, index=True)
    performed_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Actions: registered | allocated | returned | transferred | status_changed | updated
    action = Column(String(100), nullable=False)
    action_detail = Column(Text, nullable=True)

    performed_at = Column(DateTime, nullable=False)

    # Relationships
    asset = relationship("Asset", back_populates="history")
    performed_by = relationship("User", foreign_keys=[performed_by_id])
