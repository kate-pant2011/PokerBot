from app.database.table import (
    get_active_tables,
    get_table_by_id,
    add_tables,
)
from app.database.table_player import table_participants_count
from app.config.config import ApplicationException
from app.schemas.common import to_schema
from app.schemas.table import TableListResponse, TableResponse, TableCountResponse
from app.services.game import check_game_by_id
from app.schemas.common import BaseShortResponse


sorting_rules = {"number": ("number",)}


async def get_table_list(session, limit, offset, game_id, organizer_id=None):
    game = await check_game_by_id(session, game_id)

    if organizer_id is not None and organizer_id != game.organizer_id:
        raise ApplicationException("Only organizer can view tables", 403)

    tables = await get_active_tables(session, limit, offset, game_id, sorting_rules)

    result = []
    for t in tables.items:
        data = to_schema(TableCountResponse, t)
        count = await table_participants_count(session, t.id)
        data.total_participants = count
        result.append(data)

    return TableListResponse(
        items=result,
        total= tables.total,
        limit=limit,
        offset=offset,
    )


async def get_table_id(session, table_id):
    table = await get_table_by_id(session, table_id)

    if not table:
        raise ApplicationException("table Not found", 404)

    data = to_schema(TableResponse, table)

    data.players = [to_schema(BaseShortResponse, tp.player) for tp in table.table_participants]

    return data


async def create_tables(session, item, game_id, user_id):
    game = await check_game_by_id(session, game_id)

    if user_id != game.organizer_id:
        raise ApplicationException("Only organizer can create tables", 400)

    await add_tables(session, game_id, item)
    return {"result": "added"}


async def delete_table(session, table_id, user_id):
    table = await get_table_by_id(session, table_id)

    if not table:
        raise ApplicationException("table Not found", 404)

    if table.game.organizer_id != user_id:
        raise ApplicationException("Only organizer can delete tables", 400)

    await session.delete(table)

    return {"result": "deleted"}


async def change_table(session, id, item, user_id):
    table = await get_table_by_id(session, id)

    if table.game.organizer_id != user_id:
        raise ApplicationException("Only organizer can change game", 400)

    update_data = item.model_dump(exclude_unset=True)

    started_at = update_data.get("started_at", None) or table.started_at
    finished_at = update_data.get("finished_at", None) or table.finished_at

    if started_at and finished_at and started_at > finished_at:
        raise ApplicationException("End-date cannot be less than start-date", 400)

    for name, value in update_data.items():
        setattr(table, name, value)

    return to_schema(TableResponse, table)
