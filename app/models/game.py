from .base import BaseModel
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    ForeignKey,
    Enum as SQLEnum,
    UniqueConstraint,
    DateTime,
    BigInteger
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from enum import Enum


class Status(str, Enum):
    JOINED = "joined"
    LEFT = "left"


class GameStatus(str, Enum):
    AWAITED = "awaited"
    IN_ACTION = "in_action"
    CANCELED = "canceled"
    FINISHED = "finished"


class Game(BaseModel):
    __tablename__ = "games"

    name = Column(String, nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=True)
    status = Column(
        SQLEnum(GameStatus, name="game_status"),
        nullable=False,
        default=GameStatus.AWAITED,
    )
    is_archived = Column(Boolean, nullable=False, default=False, index=True)

    players = relationship("GamePlayer", back_populates="game")

    organizer_id = Column(Integer, ForeignKey("players.id"), nullable=False, index=True)
    organizer = relationship("Player", back_populates="organized_games")

    tables = relationship("Table", back_populates="game")
    elo_history = relationship("EloHistory", back_populates="game")

    telegram_chat_id = Column(BigInteger, ForeignKey("telegram_chats.chat_id"), nullable=True)
    telegram_chat = relationship("TelegramChat", back_populates="games")

    # numer of rouds чтобы потом сравнивать друг с другом сравнимых
    poll_id = Column(String, nullable=True)
    poll_register_id = Column(String, nullable=True)
    poll_exit_id = Column(String, nullable=True)
    registered = Column(Integer, nullable=True)
    

class GamePlayer(BaseModel):
    __tablename__ = "game_players"

    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    player = relationship("Player", back_populates="games")

    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    game = relationship("Game", back_populates="players")
    # list of table numbers where player sitted during game
    # is_active = Column(Boolean, default=True, nullable=False)
    # position = Column(Integer, nullable=True)
    # eliminated_by_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    # eliminator = relationship(
    #     "Player", foreign_keys=[eliminated_by_id], back_populates="eliminations"
    # )
    status = Column(
        SQLEnum(Status, name="game_player_status"),
        nullable=False,
        default=Status.JOINED,
    )

    __table_args__ = ()
