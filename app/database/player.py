from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from .common import order, get_all_and_total, apply_sorting
from app.models.player import Player


async def get_all_players(session, limit, offset, sorting_rules=None):
    stmt = select(Player).where(Player.is_archived.is_(False))

    if sorting_rules:
        stmt = apply_sorting(stmt=stmt, model=Player, sort="-elo", sorting_rules=sorting_rules)

    else:
        stmt = order(stmt=stmt, model=Player)

    result = await get_all_and_total(session, stmt, limit, offset)
    return result


async def get_player_by_id(session, player_id):
    result = await session.execute(
        select(Player)
        .options(selectinload(Player.games))
        .options(selectinload(Player.organized_games))
        .options(selectinload(Player.elo_history))
        .options(selectinload(Player.eliminations))
        .where(Player.id == player_id)
    )
    player = result.scalar_one_or_none()
    return player


async def get_player_by_tg_id(session, tg_id):
    result = await session.execute(
        select(Player)
        .options(selectinload(Player.games))
        .options(selectinload(Player.organized_games))
        .options(selectinload(Player.elo_history))
        .where(Player.telegram_id == tg_id)
    )
    player = result.scalar_one_or_none()
    return player


async def add_player(session, item, tg_id):
    player = Player(
        telegram_id=tg_id,
        name=item.name,
    )

    session.add(player)
    await session.flush()
    return player


async def reset_all_players_elo(session, elo: float = 1000):
    await session.execute(
        update(Player).values(
            elo=elo,
            elo_change_per_match=0,
        )
    )
    await session.flush()


async def mod_all_players_elo(session):
    await session.execute(
        update(Player).values(
            elo=Player.elo % 100,
        )
    )
    await session.flush()


async def set_player_elo_by_name(
    session,
    player_name: str,
    elo: float,
):
    result = await session.execute(
        update(Player)
        .where(Player.name == player_name)
        .values(elo=elo)
    )

    await session.flush()


async def recalculate_rush6_elo(session):
    placement = [
        "ksgo",
        "AnanasClassic",
        "Popit",
        "AstapovIE",
        "Denis",
        "Khadgar",
        "progiv",
        "temastian",
        "Aleksandr Lazarev",
        "papinsibiryak54",
        "4 сыра",
        "eewwaann",
        "a_gundorov",
        "lily_kurchenko",
        "Kamran",
        "GermanMax",
        "alexyalunin",
        "MeshaZa",
        "DenisChistov",
        "Lev",
        "messoem",
        "Vasilii Kozlov",
        "Санчоус",
        "Lirikl",
        "elyaishere",
        "starRlCK",
        "Passtika",
        "RaymanDaxter",
    ]

    registered = len(placement)

    for place, name in enumerate(placement, start=1):
        current_participants = place

        elo_change = (
            min(100
            * (((registered - current_participants) / (registered - 1)) ** 1.5)
            * ((registered / 15) ** 0.2), 99.9)
        )

        player = await session.scalar(
            select(Player).where(Player.name == name)
        )

        if player is None:
            print(f"Player '{name}' not found")
            continue

        player.elo = elo_change

    await session.flush()