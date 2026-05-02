from app.database.score import (
    get_elo_history_by_player,
    get_game_players_last_rating,
    create_elo_history,
)
from app.config.config import ApplicationException
from app.schemas.common import to_schema
from app.database.table import get_table_by_id
from app.database.table_player import get_all_table_players_by_id
from app.services.game import check_game_by_id
from app.schemas.score import EloHistoryResponse, TableResultResponse, EloTableResult
from app.schemas.common import BaseShortResponse
from app.models.game import GameStatus
from datetime import datetime, timezone
from collections import defaultdict

async def get_player_elo_history(session, player_id, limit, offset):
    result = await get_elo_history_by_player(session, player_id, limit, offset)

    return {
        "items": [to_schema(EloHistoryResponse, e) for e in result.items],
        "total": result.total,
        "limit": limit,
        "offset": offset,
    }


async def get_game_rating(session, game_id):
    players = await get_game_players_last_rating(session, game_id)

    return {
        "items": [
            {
                "player": to_schema(BaseShortResponse, p["player"]),
                "rating": p["rating"],
            }
            for p in players
        ]
    }


async def close_table_and_update_elo(session, table_id, user_id):
    table = await get_table_by_id(session, table_id)

    if not table:
        raise ApplicationException("Table not found", 404)

    if table.game.organizer_id != user_id:
        raise ApplicationException("Only organizer can close table", 400)

    table_players = await get_all_table_players_by_id(session, table_id)
    assign_positions(table_players)

    if not table_players:
        raise ApplicationException("No players at table", 400)

    elo_results = []
    players = [tp.player for tp in table_players]
    total_players = len(players)
    total_chips = sum(tp.chips for tp in table_players)
    avg_chips = total_chips / total_players if total_players > 0 else 0
    knockouts_map = defaultdict(list)
    players_map = {p.id: p for p in players}

    for tp in table_players:
        if tp.eliminated_by_id:
            victim_elo = tp.player.elo
            knockouts_map[tp.eliminated_by_id].append(victim_elo)
    
    for tp in table_players:
        player = tp.player

        opponents_elos = [
            p.elo for p in players if p.id != player.id
        ]

        elo_before = player.elo

        elo_change = elo_delta(
            player,
            opponents_elos,
            tp.position,
            total_players
        )

        bounty = bounty_bonus(player.id, knockouts_map, players_map)
        chips_bonus = calculate_chips_bonus(tp.chips, avg_chips)

        total_change = elo_change + bounty + chips_bonus
        elo_after = max(100, elo_before + total_change)

        player.elo = elo_after

        await create_elo_history(
            session=session,
            player_id=player.id,
            game_id=table.game_id,
            table_id=table.id,
            elo_before=round(elo_before, 2),
            elo_after=round(elo_after, 2),
            elo_change=round(elo_change, 2),
            bounty_bonus=round(bounty, 2),
            chips_bonus=chips_bonus,
            position=tp.position,
            chips=tp.chips,
            players_total=total_players,
        )

        tp.is_active = False
        tp.finished_at = datetime.now(timezone.utc)

        elo_results.append(
            EloTableResult(
                player=BaseShortResponse(
                    id=player.id,
                    name=player.name,
                ),
                game_id=table.game_id,
                elo_change=round(elo_change, 2),
                bounty_bonus=round(bounty, 2),
                chips_bonus=round(chips_bonus, 2),
                position=tp.position,
                chips=tp.chips,
            )
        )

    game = await check_game_by_id(session, table.game_id)

    open_tables = [t for t in game.tables if t.finished_at is None]

    if table.round == 1 and len(open_tables) == 1:
        game.status = GameStatus.FINISHED
        game.is_archived = True

    table.finished_at = datetime.now(timezone.utc)
    await session.flush()

    elo_results.sort(key=lambda x: x["position"])

    return TableResultResponse(
        id=table.id,
        number=table.number,
        game_id=table.game_id,
        chat_id=game.telegram_chat_id or None,
        thread_id=game.telegram_chat.thread_id or None,
        elo_history=elo_results,
         
     )


def elo_delta(player, opponents, position, total_players):
    s = actual_score(position, total_players)
    e = expected_score(player.elo, opponents)
    k = k_factor(player.games_played, player.elo)
    return k * (s - e)

def bounty_bonus(player_id, knockouts_map, players_map):
    victims = knockouts_map.get(player_id, [])
    bonus = 0.0
    for v_elo in victims:
        raw = 5 + (v_elo - players_map[player_id].elo) / 100
        bonus += max(2, raw)
    return bonus

def expected_score(player_elo, opponents):
    if not opponents:
        return 0.5
    return sum(
        1 / (1 + 10 ** ((opp - player_elo) / 400))
        for opp in opponents
    ) / len(opponents)

def actual_score(position, total):
    if total <= 1:
        return 1.0

    base_score = (total - position) / (total - 1)
    return 0.1 + (base_score * 0.8)

def k_factor(games_played, elo):
    if games_played < 10:
        return 30 
    if elo < 1400:
        return 15
    return 10

def calculate_chips_bonus(player_chips: int, avg_chips: float) -> float:
    if avg_chips == 0 or player_chips <= avg_chips:
        return 0.0
    
    bonus = ((player_chips - avg_chips) / avg_chips) * 10.0
    return round(bonus, 2)


def assign_positions(table_players):
    placed = [tp for tp in table_players if tp.position is not None]
    active = [tp for tp in table_players if tp.position is None]

    active.sort(key=lambda x: x.chips, reverse=True)

    current_position = 1

    for tp in active:
        tp.position = current_position
        current_position += 1

