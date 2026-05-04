from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from .common import get_all_and_total
from app.models.score import EloHistory
from app.models.player import Player
from app.models.table import Table

async def get_elo_history_by_player(session, player_id, limit, offset):
    stmt = (
        select(EloHistory)
        .options(selectinload(EloHistory.player))
        .options(selectinload(EloHistory.game))
        .options(selectinload(EloHistory.table))
        .where(EloHistory.player_id == player_id)
        .order_by(EloHistory.created_at.desc())
    )

    return await get_all_and_total(session, stmt, limit, offset)


async def get_game_players_last_rating(session, game_id):
    subquery = (
        select(EloHistory.player_id, func.max(EloHistory.id).label("max_id"))
        .where(EloHistory.game_id == game_id)
        .group_by(EloHistory.player_id)
        .subquery()
    )

    stmt = (
        select(Player, EloHistory.elo_after)
        .join(subquery, subquery.c.player_id == Player.id)
        .join(EloHistory, EloHistory.id == subquery.c.max_id)
    )

    result = await session.execute(stmt)

    return [{"player": row[0], "rating": row[1]} for row in result.all()]


async def create_elo_history(       
        session,
        player_id,
        game_id,
        table_id,
        elo_before,
        elo_after,
        elo_change,
        bounty_bonus,
        chips_bonus,
        position,
        chips,
        players_total,
):
    elo = EloHistory(
        player_id=player_id,
        game_id=game_id,
        table_id=table_id,
        elo_before=elo_before,
        elo_after=elo_after,
        elo_change=elo_change,
        bounty_bonus=bounty_bonus,
        chips_bonus=chips_bonus,
        players_total=players_total,
        position=position,
        chips=chips,
    )

    session.add(elo)
    await session.flush()


