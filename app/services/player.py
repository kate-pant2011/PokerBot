from app.database.player import (
    get_all_players,
    get_player_by_tg_id,
    get_player_by_id,
    add_player,
)
from app.database.game import get_active_game, get_game_players
from app.database.table_player import get_active_player_table, get_table_players_by_id, get_active_table_map, get_player_chips_map
from app.config.config import ApplicationException
from app.schemas.player import PlayerResponse, LeaderBoardListResponse, MyTableResponse, TablePlayerInfo
from app.schemas.common import BaseShortResponse, ResultResponse, to_schema

sorting_rules = {"elo": ("elo", "created_at")}


async def check_player_by_id(session, id):
    player = await get_player_by_id(session, id)

    if not player:
        raise ApplicationException("Player Not found", 404)

    if player.is_archived:
        raise ApplicationException(f"A player '{player.name}' is archived", 400, {"id": player.id})

    return to_schema(BaseShortResponse, player)


async def check_player_tg_id(session, tg_id):
    player = await get_player_by_tg_id(session, tg_id)

    if not player:
        raise ApplicationException("Player Not found", 404)

    if player.is_archived:
        raise ApplicationException(f"A player '{player.name}' is archived", 400, {"id": player.id})

    return to_schema(BaseShortResponse, player)


async def get_player_list(session, limit, offset):
    players = await get_all_players(session, limit, offset)

    if not players.items:
        raise ApplicationException("Player List Not found", 404)

    return {
        "items": [to_schema(BaseShortResponse, p) for p in players.items],
        "total": players.total,
        "limit": limit,
        "offset": offset,
    }


async def get_leaderboard(session, limit, offset):
    sorting_rules = {"elo": ("elo","name")}
    players = await get_all_players(session, limit, offset, sorting_rules)

    if not players.items:
        raise ApplicationException("Player List Not found", 404)

    return LeaderBoardListResponse(
        items=players.items,
        total=players.total,
        limit=limit,
        offset=offset,
    )


async def get_player_id(session, player_id):
    player = await check_player_by_id(session, player_id)

    if not player:
        raise ApplicationException("Player not found", 404)

    data = PlayerResponse(
        id=player.id,
        telegram_id=player.telegram_id,
        name=player.name,
        elo=player.elo,
        organized_games=[to_schema(BaseShortResponse, g) for g in player.organized_games],
        total_games=len(player.games) or 0,
        total_knockouts=len(player.eliminations) or 0,
    )

    return data


async def create_player(session, item, tg_id):
    player = await get_player_by_tg_id(session, tg_id)

    if player:
        if player.is_archived:
            raise ApplicationException(
                f"A player '{player.name}' is archived", 400, {"id": player.id}
            )

        raise ApplicationException("Player with such telegram already exists", 400)

    new_player = await add_player(session, item, tg_id)
    return to_schema(BaseShortResponse, new_player)


async def change_player(session, id, item, user_id):
    player = await check_player_by_id(session, id)

    if player.id != user_id:
        raise ApplicationException("Only personal data can be changed", 400)

    update_data = item.model_dump(exclude_unset=True)

    for name, value in update_data.items():
        setattr(player, name, value)

    return ResultResponse(result="changed")


async def archive_player(session, id, user_id):
    player = await get_player_by_id(session, id)

    if not player:
        raise ApplicationException("player Not found", 404)

    if player.id != user_id:
        raise ApplicationException("Only personal data can be changed", 400)

    if player.is_archived:
        raise ApplicationException(f"A player {player.name} is archived", 400)

    player.is_archived = True
    return player


async def restore_player(session, id, user_id):
    player = await get_player_by_id(session, id)

    if not player:
        raise ApplicationException("Player Not found", 404)

    if player.id != user_id:
        raise ApplicationException("Only personal data can be changed", 400)

    if not player.is_archived:
        raise ApplicationException("Player is already active", 400)

    player.is_archived = False
    return player


async def get_my_table(session, player_id):
    game = await get_active_game(session)
    if not game:
        raise ApplicationException("No active game", 404)

    table_player = await get_active_player_table(session, player_id, game.id)

    if table_player:
        table = table_player.table
        players = await get_table_players_by_id(session, table.id)

        return MyTableResponse(
            scope="table",
            table_id=table.id,
            table_number=table.number, 
            players=[
                TablePlayerInfo(
                    id=tp.player.id,
                    name=tp.player.name,
                    chips=tp.chips or 0,
                    table_id=table.id
                )
                for tp in players
            ]           
        )
    if game.organizer_id == player_id:
        players_data = await get_game_players(session, game.id, limit=50, offset=0)

        players = players_data.items or []
        table_map = await get_active_table_map(session, game.id)
        chips_map = await get_player_chips_map(session, game.id)

        return MyTableResponse(
            scope="game",
            table_id= None,
            table_number= None, 
            players=[
                TablePlayerInfo(
                    id=p.player.id,
                    name= p.player.name,
                    chips=chips_map.get(p.player.id, 0),
                    table_id=table_map.get(p.player.id)
                )
                for p in players
            ]           
        )

    else:
        raise ApplicationException("Player not at table", 404)

