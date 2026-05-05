from app.database.game import (
    get_all_games,
    get_game_by_id,
    add_game,
    add_to_game,
    get_game_players,
    is_player_in_game,
    get_game_players_count,
)
from app.database.table_player import get_active_player_table, add_table_players
from app.config.config import ApplicationException
from app.schemas.common import to_schema, BaseListResponse, BaseShortResponse, ResultResponse
from app.schemas.game import GameResponse, GamePlayerList, DistributeTablesResponse, TableDistribute, TablePlayerDistribute
from datetime import datetime, timezone
from app.models.game import Status, GameStatus
from app.database.table import add_tables, get_all_tables, add_table
from app.services.player import check_player_tg_id
from sqlalchemy.exc import IntegrityError
import math
from dataclasses import dataclass

@dataclass
class NewTablesDTO:
    total_tables: int
    round: int


async def check_game_by_id(session, id):
    game = await get_game_by_id(session, id)

    if not game:
        raise ApplicationException("game Not found", 404)

    if game.is_archived:
        raise ApplicationException(f"A game '{game.name}' is archived", 400, {"id": game.id})

    return game


async def get_game_list(session, limit, offset, status=None, organizer_id=None):

    if organizer_id:
        organizer = await check_player_tg_id(session, organizer_id)
        organizer_id = organizer.id

    games = await get_all_games(session, limit, offset, status, organizer_id)

    return BaseListResponse(
        items=games.items,
        total=games.total,
        limit=limit,
        offset=offset,
    )

async def get_game_players_list(session, game_id, limit, offset):
    game_players = await get_game_players(session, game_id, limit, offset)

    return GamePlayerList(
        items=game_players.items,
        total=game_players.total,
        limit=limit,
        offset=offset,
    )

async def get_game_id(session, id):
    game = await check_game_by_id(session, id)

    return to_schema(GameResponse, game)


async def create_game(session, item, user_id):
    new_game = await add_game(session, item, user_id)

    return to_schema(BaseShortResponse, new_game)


async def change_game(session, id, item, user_id):
    game = await check_game_by_id(session, id)

    if game.organizer_id != user_id:
        raise ApplicationException("Only organizer can change game", 400)

    update_data = item.model_dump(exclude_unset=True)

    start_time = update_data.get("start_time", None) or game.start_time

    if start_time:
        if start_time < datetime.now():
            raise ApplicationException("Cannot start game earlier than now", 400)

    for name, value in update_data.items():
        setattr(game, name, value)

    return to_schema(GameResponse, game)


async def join_game(session, game_id, player_id):
    await check_game_by_id(session, game_id)

    in_game = await is_player_in_game(session, player_id, game_id)

    if in_game:
        if in_game.status == Status.JOINED:
            existing = await get_active_player_table(session, player_id, game_id)
            if existing:
                raise ApplicationException(
                    f"Player already joined table number {existing.table.number}",
                    400,
                )
            raise ApplicationException("Player already joined game", 400)
            
        elif in_game.status == Status.LEFT:
            in_game.status = Status.JOINED
            return ResultResponse(result="joined")
        
        else:
            return ResultResponse(result="it breaks here")
    
    try:
        await add_to_game(session=session, game_id=game_id, player_id=player_id)

    except IntegrityError as e:
        raise ApplicationException(f"SQL Error: {e}", 400)

    return ResultResponse(result="joined")


async def leave_game(session, game_id, player_id):
    await check_game_by_id(session, game_id)

    in_game = await is_player_in_game(session, player_id, game_id)

    if not in_game:
        raise ApplicationException("Player is not in the game", 400)

    else:
        existing = await get_active_player_table(session, player_id, game_id)

        if existing:
            raise ApplicationException(
                f"To leave game please leave table {existing.table.number}", 400
            )

    in_game.status = Status.LEFT

    return ResultResponse(result="left")


async def archive_game(session, id, user_id):
    game = await get_game_by_id(session, id)

    if not game:
        raise ApplicationException("Game not found", 404)

    if game.organizer_id != user_id:
        raise ApplicationException("Only organizer can archive game", 400)

    if game.is_archived:
        raise ApplicationException(f"Game {game.name} is archived", 400)

    game.is_archived = True
    return game


async def restore_game(session, id, user_id):
    game = await get_game_by_id(session, id)

    if not game:
        raise ApplicationException("Game not found", 404)

    if game.organizer_id != user_id:
        raise ApplicationException("Only organizer can change game", 400)

    if not game.is_archived:
        raise ApplicationException("Game is already active", 400)

    game.is_archived = False
    return game


async def distribute_tables(session, game_id, user_id):
    game = await check_game_by_id(session, game_id)

    if game.organizer_id != user_id:
        raise ApplicationException("Only organizer can distribute tables", 400)
    
    sorting_rules = {"number": ("number",)}
    tables = await get_all_tables(
        session=session, limit=20, offset=0, game_id=game_id, sorting_rules=sorting_rules
    )
    tables = tables.items
    if not tables:
        round_number = 1
    
    if any(t.round == 1 for t in tables):
        raise ApplicationException("The max round-numbers is one, cannot start new round", 400)

    game.start_time = datetime.now(timezone.utc)
    game.status = GameStatus.IN_ACTION


    players_number = await get_game_players_count(session, game_id)

    if players_number < 20:
        tables_size_list = split_tables(players=players_number, max_per_table=6)

    else:
        tables_size_list = split_tables(players=players_number, max_per_table=8)
    
    '''
    new_table_item = NewTablesDTO(
        total_tables=len(tables_size_list), round=round_number
    )
    new_tables = await add_tables(session=session, game_id=game_id, item=new_table_item)
    '''

    new_table = await add_table(session, game_id, 1, round_number)

    sorting = {"elo": ("elo",)}
    players = await get_game_players(
        session=session, game_id=game_id, limit=100, offset=0, sort="-elo", sorting_rules=sorting
    )

    await add_table_players(session=session, table=new_table, size_list=tables_size_list, players=players)

    fictitious_distribution = await  fictitious_table_players(players, tables_size_list, new_table.id, round_number)
    '''
    await session.commit()
    session.expire_all()
    updated_game = await get_game_by_id(session, game_id)
    '''

    return await build_distribute_response(game, fictitious_distribution)


def split_tables(players: int, max_per_table: int):
    tables = math.ceil(players / max_per_table)
    
    base = players // tables
    remainder = players % tables
    
    result = [base + 1] * remainder + [base] * (tables - remainder)
    
    return result


async def fictitious_table_players(players, size_list, real_table_id, round_val):
    start = 0
    tables_distribution = []
    flat_players = players.items

    for idx, size in enumerate(size_list, start=1):
        current_table_players = [] 
        
        for i in range(size):
            if start < len(flat_players):
                player_data = flat_players[start]
                
                current_table_players.append(TablePlayerDistribute(
                    id=player_data.player_id,
                    name=player_data.player.name,
                    telegram_id=player_data.player.telegram_id,
                ))
                start += 1

        tables_distribution.append(TableDistribute(
            id=real_table_id, 
            number=idx,       
            round=round_val,
            players=current_table_players
        ))
            
    return tables_distribution

async def build_distribute_response(game, tables_distribution):
    return DistributeTablesResponse(
        game_id=game.id,
        chat_id=game.telegram_chat_id or None,
        thread_id=game.telegram_chat.thread_id if game.telegram_chat else None,
        tables=tables_distribution
    )

'''
async def build_distribute_response(game, tables):
    return DistributeTablesResponse(
        game_id=game.id,
        chat_id=game.telegram_chat_id or None,
        thread_id=game.telegram_chat.thread_id if game.telegram_chat else None,
        tables=[
            TableDistribute(
                id=table.id,
                number=table.number,
                round=table.round,
                players=[
                    TablePlayerDistribute(
                        id=tp.player.id,
                        name=tp.player.name,
                        telegram_id=tp.player.telegram_id,
                    )
                    for tp in table.table_participants
                ]
            )
            for table in tables if table.finished_at is None
        ],
    )
'''