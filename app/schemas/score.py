from pydantic import BaseModel, ConfigDict
from .common import BaseShortResponse
from .table import TableShortResponse
from datetime import datetime


class EloHistoryResponse(BaseModel):
    id: int
    player: BaseShortResponse
    game: BaseShortResponse
    table: TableShortResponse

    elo_before: float
    elo_after: float
    elo_change: float | None

    bounty_bonus: float | None
    players_total: int | None
    position: int | None
    chips: int

    model_config = ConfigDict(from_attributes=True)


class EloListResponse(BaseModel):
    items: list[EloHistoryResponse]
    total: int
    limit: int
    offset: int


class PlayerRatingResponse(BaseModel):
    player: BaseShortResponse
    rating: float | None


class RatingListResponse(BaseModel):
    items: list[PlayerRatingResponse]


class EloTableResult(BaseModel):
    player: BaseShortResponse
    game_id: int
    elo_change: float
    bounty_bonus: float
    chips_bonus: float
    position: int
    chips: int
    finished_at: datetime


class TableResultResponse(BaseModel):
    id: int
    number: int
    game_id: int
    game_name: str
    chat_id: int | None
    thread_id: int | None
    elo_history: list[EloTableResult]
