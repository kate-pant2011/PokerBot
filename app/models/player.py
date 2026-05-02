from .base import BaseModel
from sqlalchemy import Column, Integer, String, Boolean, Float, BigInteger
from sqlalchemy.orm import relationship


class Player(BaseModel):
    __tablename__ = "players"

    name = Column(String, nullable=False, unique=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    elo = Column(Float, default=1000)

    is_archived = Column(Boolean, nullable=False, default=False, index=True)

    games = relationship("GamePlayer", back_populates="player")
    games_played = Column(Integer, nullable=False, default=0)

    organized_games = relationship("Game", back_populates="organizer")
    table_participations = relationship("TablePlayer", foreign_keys="TablePlayer.player_id", back_populates="player")

    eliminations = relationship("TablePlayer", foreign_keys="TablePlayer.eliminated_by_id", back_populates="eliminator")
    elo_history = relationship("EloHistory", back_populates="player")

    telegram_chats = relationship("TelegramChat", back_populates="activator")