from .base import BaseModel
from sqlalchemy import Column, Boolean, Integer, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship


class TablePlayer(BaseModel):
    __tablename__ = "table_players"

    player_id = Column(Integer, ForeignKey("players.id"), nullable=False, index=True)
    player = relationship("Player", foreign_keys=[player_id], back_populates="table_participations")

    table_id = Column(
        Integer, ForeignKey("tables.id", ondelete="CASCADE"), nullable=True, index=True
    )
    table = relationship("Table", back_populates="table_participants")

    started_at = Column(DateTime(timezone=True), nullable=False) # можно сделать неважным
    finished_at = Column(DateTime(timezone=True), nullable=True) # можно сделать неважным
    is_active = Column(Boolean, default=True, nullable=False)

    position = Column(Integer, nullable=True)
    chips = Column(Integer, nullable=False, default=0)

    eliminated_by_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    eliminator = relationship(
        "Player", foreign_keys=[eliminated_by_id], back_populates="eliminations"
    )

    __table_args__ = ()
