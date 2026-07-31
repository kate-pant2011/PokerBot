from app.database.game import (
    get_all_games,
    get_game_by_id,
    add_game,
    add_to_game,
    get_game_players,
    is_player_in_game,
    get_game_players_count,
)
from app.database.table_player import (
    get_active_player_table,
    add_table_players,
    add_table_player,
    get_all_table_players_by_id)
from app.config.config import ApplicationException
from app.schemas.common import to_schema, BaseListResponse, BaseShortResponse, ResultResponse
from app.schemas.game import GameResponse, GamePlayerList, DistributeTablesResponse, TableDistribute, TablePlayerDistribute
from datetime import datetime, timezone
from app.models.game import Status, GameStatus
from app.database.table import add_tables, get_all_tables, add_table, get_active_tables
from app.database.common import ORMListResult
from app.services.player import check_player_tg_id, get_player_by_id, get_my_table
from sqlalchemy.exc import IntegrityError
import math
import random
from dataclasses import dataclass

@dataclass
class NewTablesDTO:
    total_tables: int


async def check_game_by_id(session, id):
    print(f"\n⚠️⚠️⚠️ BEFORE GET GAME BY ID\n")
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


async def create_game(session, item, user_id, poll_register_id, poll_exit_id, registered):
    new_game = await add_game(session, item, user_id, poll_register_id, poll_exit_id, registered)

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
    game = await check_game_by_id(session, game_id)
    player = await get_player_by_id(session, player_id)
    player.elo_change_per_match = 0
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
            return ResultResponse(result="✅ Ты присоединился")
        
        else:
            return ResultResponse(result="it breaks here")
    text = ''
    try:
        print("BEFORE ADDING TO GAME")
        await add_to_game(session=session, game_id=game_id, player_id=player_id)
        print(f"\n GAME STATUS WHEN JOIN DURING GAME {game.status} \n ")
        if game.status == GameStatus.IN_ACTION:
            print("INSIDE IF")
            sorting_rules = {"number": ("number",)}
            tables = await get_active_tables(
                session=session, limit=1000, offset=0, game_id=game_id, sorting_rules=sorting_rules
            )
            print("GoT ACTIVE TABLES")
            tables = tables.items
            table_ = tables[0]
            # min_change = 100
            # for table in tables:
            #     curr_min = 0
            #     print("BEFORE TAKE TABLE PLAYERS")
            #     table_players = await get_all_table_players_by_id(session, table.id)
            #     print("AFTER TAKE TABLE PLAYERS")
            #     for player in table_players:
            #         curr_min += player.player.elo_change_per_match
            #     print("AFTER CURR MIN")
            #     if curr_min < min_change and len(table_players) < 2:
            #         table_ = table
            #         min_change = curr_min
            print("BEFORE ADD TABLE")
            if table_:
                table_player = await add_table_player(session, table_.id, player_id)
                text = f"🪑Двигай за свободное место"
                print(f"\nTABLE ID for newcommer{table_.id}\n")
            else:
                text = f"Попроси организатора перемешать столы 🪑, время пришло"
            

    except IntegrityError as e:
        raise ApplicationException(f"SQL Error: {e}", 400)

    return ResultResponse(result=text if text else "✅ Ты присоединился")


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
    print("GAME CHECKED")

    if game.organizer_id != user_id:
        raise ApplicationException("Only organizer can distribute tables", 400)
    
    # sorting_rules = {"number": ("number",)}
    # tables = await get_all_tables(
    #     session=session, limit=20, offset=0, game_id=game_id, sorting_rules=sorting_rules
    # )
    # tables = tables.items

    game.start_time = datetime.now(timezone.utc)
    game.status = GameStatus.IN_ACTION

    players_number = await get_game_players_count(session, game_id)
    print("PLAYERS COUNTED")

    tables_size_list = split_tables(players=players_number, max_per_table=8)
    
    # new_table_item = NewTablesDTO(
    #     total_tables=len(tables_size_list)
    # )
    #new_tables = await add_tables(session=session, game_id=game_id, item=new_table_item)
    new_table = await add_table(session, game_id, 1)
    print("TABLES ADDED")


    sorting = {"elo": ("elo",)}
    players = await get_game_players(
        session=session, game_id=game_id, limit=1000, offset=0, sort="-elo", sorting_rules=sorting
    )

    for player in players.items:
        player.player.elo_change_per_match = 0
    await session.flush()

    await add_table_players(session=session, table=new_table, size_list=tables_size_list, players=players)
    print("TABLE PLAYERS ADDED")

    fictitious_distribution = await fictitious_table_players(players, tables_size_list, new_table.id)
    print("TABLE PLAYERS ADDED")
    await session.flush()
    updated_game = await get_game_by_id(session, game_id)
    print("AFTER FLUSH")

    #return await build_distribute_response(updated_game, new_tables)
    return await build_distribute_response(updated_game, fictitious_distribution)


async def distribute_tables_for_shuffle(session, game_id, user_id, active_players, table_id):
    game = await check_game_by_id(session, game_id)
    print("GAME CHECKED")

    if game.organizer_id != user_id:
        raise ApplicationException("Only organizer can distribute tables", 400)

    #table = await get_my_table(session, user_id)
    players_number = len(active_players)
    print("\n Table GOT\n")
    tables_size_list = split_tables(players=players_number, max_per_table=8)

    fictitious_distribution = await fictitious_table_players(active_players, tables_size_list, table_id)
    await session.flush()
    updated_game = await get_game_by_id(session, game_id)

    return await build_distribute_response(updated_game, fictitious_distribution)


def split_tables(players: int, max_per_table: int):
    tables = math.ceil(players / max_per_table)
    
    base = players // tables
    remainder = players % tables
    
    result = [base + 1] * remainder + [base] * (tables - remainder)
    
    return result



async def fictitious_table_players(players, size_list, real_table_id):
    start = 0
    tables_distribution = []
    if isinstance(players, list):
        flat_players = players
    else:
        flat_players = players.items
    random.shuffle(flat_players)

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