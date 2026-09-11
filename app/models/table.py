from .base import BaseModel
from sqlalchemy import Column, Integer, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship


class Table(BaseModel):
    __tablename__ = "tables"

    number = Column(Integer, nullable=False)

    started_at = Column(DateTime(timezone=True), nullable=True) #неважго теперь
    finished_at = Column(DateTime(timezone=True), nullable=True) #неважго теперь

    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    game = relationship("Game", back_populates="tables")

    table_participants = relationship("TablePlayer", back_populates="table", passive_deletes=True)

    elo_history = relationship("EloHistory", back_populates="table")

    __table_args__ = ()
