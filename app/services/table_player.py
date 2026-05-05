from app.config.config import ApplicationException
from app.schemas.common import to_schema, ResultResponse
from app.schemas.table_player import TablePlayerResponse, TablePlayerKnockout
from app.services.player import check_player_by_id
from app.services.game import check_game_by_id
from datetime import datetime, timezone
from app.database.table import get_table_by_id
from app.database.table_player import (
    get_table_players_by_id,
    add_table_player,
    get_table_player_by_id,
    get_table_player_count,
    get_active_player_table,
    table_participants_count,
)
from sqlalchemy.exc import IntegrityError
from app.models.game import Status


async def get_table_players(session, table_id):
    table = await get_table_by_id(session, table_id)

    if not table:
        raise ApplicationException("table Not found", 404)

    table_players = await get_table_players_by_id(session, table_id)

    count = await table_participants_count(session, table_id)

    result = []
    for tp in table_players:
        data = to_schema(TablePlayerResponse, tp)
        data.table_participants = count
        result.append(data)

    return result


async def add_player_at_table(session, player_id, table_id=None):
    table = await get_table_by_id(session, table_id)

    if not table:
        raise ApplicationException("table Not found", 404)

    if not any(
        gp.player_id == player_id and gp.status == Status.JOINED for gp in table.game.players
    ):
        raise ApplicationException("Player not in game", 400)

    existing = await get_active_player_table(session, player_id, table.game_id)

    if existing:
        raise ApplicationException(
            f"Please leave table #{existing.table.number} before joining a new one", 400
        )

    already_involved = await get_table_player_count(session, player_id, table.game_id)

    #if already_involved >= 2:
        #raise ApplicationException("Exceeded maximum game-attempts per game Limit - 2", 400)

    total_participants = await table_participants_count(session, table_id)

    #if total_participants >= 9:
        #raise ApplicationException("Exceeded maximum participants for table Limit - 9", 400)

    try:
        table_player = await add_table_player(session, table_id, player_id)

    except IntegrityError:
        await session.rollback()
        raise ApplicationException("Cannot join the same table twice per game", 400)

    return ResultResponse(result="joined")


async def patch_table_rights(session, table_id, user_id, player_id):
    table = await get_table_by_id(session, table_id)

    if not table:
        raise ApplicationException("table Not found", 404)

    table_player = await get_table_player_by_id(session, table_id, player_id)

    if not table_player:
        raise ApplicationException("Player not found at table", 404)

    if player_id == user_id:
        raise ApplicationException(f"Player cannot choose himself", 400)
    
    table_player_rights = await get_table_player_by_id(session, table_id, user_id)

    if user_id != table.game.organizer_id:
        if not table_player_rights:
            raise ApplicationException(f"Only table players can remove others", 404)

        return table_player, "table_player"

    if table_player_rights:
        return table_player, "table_player"
    else:
        return table_player, "organizer"


async def leave_table(session, item, table_id, user_id, player_id, user_name):
    table_player, user_rights = await patch_table_rights(session, table_id, user_id, player_id)

    finished_at = datetime.now(timezone.utc)

    if table_player.started_at > finished_at:
        raise ApplicationException("End-date cannot be less than start-date", 400)

    total_participants = await table_participants_count(session, table_id)

    table_player.finished_at = finished_at
    table_player.is_active = False
    if item.chips:
        table_player.chips = item.chips or 0
    table_player.position = total_participants

    if item.eliminated:
        if user_rights == "organizer":
            raise ApplicationException("Organizer cannot mark elimination", 400)

        table_player.eliminated_by_id = user_id

    data = to_schema(TablePlayerKnockout, table_player)

    data.table_participants = total_participants
    data.eliminator_name = user_name

    return data


async def change_table_player(session, item, table_id, user_id, player_id):
    table_player, user_rights = await patch_table_rights(session, table_id, user_id, player_id)

    total_participants = await table_participants_count(session, table_id)
    table_player.chips = item.chips or 0

    data = to_schema(TablePlayerResponse, table_player)

    data.table_participants = total_participants

    return data
