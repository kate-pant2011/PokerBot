from pydantic import BaseModel, ConfigDict, Field, field_serializer
from .common import BaseShortResponse, to_moscow
from .table import TableShortResponse
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Literal


class TablePlayerShort(BaseModel):
    id: int

    model_config = ConfigDict(from_attributes=True)


class TablePlayerResponse(BaseModel):
    id: int
    player: BaseShortResponse
    table: TableShortResponse
    started_at: datetime
    finished_at: datetime | None
    is_active: bool
    position: int | None
    chips: int
    table_participants: int | None = None

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("started_at", "finished_at")
    def serialize_datetime(self, dt):
        return to_moscow(dt)

class PlayerKnockoutResponse(BaseModel):
    id: int
    name: str
    telegram_id: int 

    model_config = ConfigDict(from_attributes=True)


class TablePlayerKnockout(BaseModel):
    id: int
    player: PlayerKnockoutResponse
    table: TableShortResponse
    started_at: datetime
    finished_at: datetime | None
    is_active: bool
    position: int | None
    chips: int
    eliminator_name: str | None = None
    table_participants: int | None = None

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("started_at", "finished_at")
    def serialize_datetime(self, dt):
        return to_moscow(dt)
    

class TablePlayerPatch(BaseModel):
    chips: int | None = Field(None, ge=0)
    eliminated: Literal[True] | None = None

    model_config = {"extra": "forbid"}
