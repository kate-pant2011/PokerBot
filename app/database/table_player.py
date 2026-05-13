from app.models.table_player import TablePlayer
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.models.table import Table
from app.models.game import Game
from app.models.player import Player
from datetime import datetime, timezone


async def get_table_players_by_id(session, table_id):
    result = await session.execute(
        select(TablePlayer)
        .options(selectinload(TablePlayer.player))
        .options(selectinload(TablePlayer.table))
        .where(TablePlayer.table_id == table_id)
        .where(TablePlayer.is_active.is_(True))
    )
    table_players = result.scalars().all()
    return table_players


async def get_table_player_by_id(session, table_id, user_id):
    result = await session.execute(
        select(TablePlayer)
        .options(selectinload(TablePlayer.player).selectinload(Player.elo_history))
        .options(selectinload(TablePlayer.table))
        .options(selectinload(TablePlayer.eliminator))
        .where(TablePlayer.table_id == table_id)
        .where(TablePlayer.player_id == user_id)
        .where(TablePlayer.is_active == True)
    )
    table_player = result.scalar_one_or_none()
    return table_player

async def get_all_table_players_by_id(session, table_id):
    result = await session.execute(
        select(TablePlayer)
        .options(selectinload(TablePlayer.player))
        .options(selectinload(TablePlayer.table))
        .where(TablePlayer.table_id == table_id)
    )
    result = result.order_by(TablePlayer.chips)
    table_players = result.scalars().all()
    return table_players


async def add_table_player(session, table_id, player_id):
    table_player = TablePlayer(table_id=table_id, player_id=player_id, started_at=datetime.now(timezone.utc))
    session.add(table_player)

    await session.flush()

    return table_player

async def add_table_players(session, table, size_list, players):
    start = 0
    flat_players = players.items

    for size in size_list:
        for i in range(size):
            player = flat_players[start]

            table_player = TablePlayer(
                table_id=table.id,
                player_id=player.player_id,
                started_at=datetime.now(timezone.utc)
            )

            session.add(table_player)
            start += 1

    await session.flush()

'''
async def add_table_players(session, tables, size_list, players):
    start = 0
    flat_players = players.items

    for table, size in zip(tables, size_list):
        for i in range(size):
            player = flat_players[start]

            table_player = TablePlayer(
                table_id=table.id,
                player_id=player.player_id,
                started_at=datetime.now(timezone.utc)
            )

            session.add(table_player)
            start += 1

    await session.flush()
'''

async def get_table_player_count(session, player_id, game_id):
    result = await session.execute(
        select(func.count(TablePlayer.id))
        .where(TablePlayer.player_id == player_id)
        .join(Table, Table.id == TablePlayer.table_id)
        .where(Table.game_id == game_id)
    )
    return result.scalar() or 0


async def table_participants_count(session, table_id):
    result = await session.execute(
        select(func.count(TablePlayer.id))
        .where(TablePlayer.table_id == table_id)
        .where(TablePlayer.is_active.is_(True))
    )
    return result.scalar() or 0


async def get_active_player_table(session, player_id, game_id):
    result = await session.execute(
        select(TablePlayer)
        .options(selectinload(TablePlayer.table))
        .where(TablePlayer.player_id == player_id)
        .where(TablePlayer.is_active.is_(True))
        .where(TablePlayer.table.has(game_id=game_id))
    )

    table_player = result.scalars().first()
    return table_player


async def get_active_table_map(session, game_id):
    result = await session.execute(
        select(TablePlayer.player_id, TablePlayer.table_id)
        .join(Table)
        .where(TablePlayer.is_active.is_(True))
        .where(Table.game_id == game_id)
    )

    return {player_id: table_id for player_id, table_id in result.all()}


async def get_player_chips_map(session, game_id):
    result = await session.execute(
        select(TablePlayer.player_id, TablePlayer.chips)
        .join(Table)  
        .where(TablePlayer.is_active.is_(True))
        .where(Table.game_id == game_id)
    )

    return {player_id: chips for player_id, chips in result.all()}