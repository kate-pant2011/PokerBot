from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.config import ApplicationException
from app.config.connection import get_db, get_db_manual
from app.services.game import (
    create_game,
    change_game,
    archive_game,
    restore_game,
    get_game_id,
    join_game,
    leave_game,
    distribute_tables,
    get_game_list,
    get_game_players_list,
)
from app.schemas.game import (
    GameResponse,
    GameAddRequest,
    GamePatchRequest,
    GamePlayerList,
    DistributeTablesResponse,
)
from app.schemas.common import BaseShortResponse, BaseListResponse, ResultResponse
from app.services.player import check_player_tg_id
from typing import Literal

game_router = APIRouter()


@game_router.get("/games", response_model=BaseListResponse)
async def get_game_list_router(
    organizer_tg_id: int | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    tg_id: int = Query(description="checking active player"),
    status: Literal["awaited", "in_action", "canceled"] | None = Query(default=None),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0),
):
    try:
        await check_player_tg_id(session, tg_id)
        return await get_game_list(
            session=session, limit=limit, offset=offset, organizer_id=organizer_tg_id, status=status
        )

    except ApplicationException as e:
        raise HTTPException(status_code=e.code, detail=e.name)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f" {type(e).__name__} - {e}")


@game_router.get("/games/{game_id}/players", response_model=GamePlayerList)
async def get_game_players_router(
    game_id: int,
    session: AsyncSession = Depends(get_db),
    tg_id: int = Query(description="checking active player"),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0),
):
    try:
        await check_player_tg_id(session, tg_id)
        return await get_game_players_list(
            session=session, game_id=game_id, limit=limit, offset=offset
        )

    except ApplicationException as e:
        raise HTTPException(status_code=e.code, detail=e.name)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f" {type(e).__name__} - {e}")


@game_router.get("/games/{id}", response_model=GameResponse)
async def get_game_router(
    id: int,
    tg_id: int = Query(description="checking active player"),
    session: AsyncSession = Depends(get_db),
):
    try:
        await check_player_tg_id(session, tg_id)
        return await get_game_id(session, id)

    except ApplicationException as e:
        raise HTTPException(status_code=e.code, detail={"message": e.name, "payload": e.payload})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f" {type(e).__name__} - {e}")


@game_router.patch("/games/{id}", response_model=GameResponse)
async def change_game_router(
    id: int,
    item: GamePatchRequest,
    tg_id: int = Query(description="checking active player"),
    session: AsyncSession = Depends(get_db),
):
    try:
        user = await check_player_tg_id(session, tg_id)
        return await change_game(session, id, item, user.id)

    except ApplicationException as e:
        raise HTTPException(status_code=e.code, detail={"message": e.name, "payload": e.payload})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f" {type(e).__name__} - {e}")


@game_router.post("/games", response_model=BaseShortResponse)
async def create_game_router(
    item: GameAddRequest,
    tg_id: int = Query(description="checking active player"),
    session: AsyncSession = Depends(get_db),
):
    try:
        user = await check_player_tg_id(session, tg_id)
        return await create_game(session, item, user.id)

    except ApplicationException as e:
        raise HTTPException(status_code=e.code, detail={"message": e.name, "payload": e.payload})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__} - {e}")


@game_router.delete("/games/{id}", response_model=BaseShortResponse)
async def archive_game_router(
    id: int,
    tg_id: int = Query(description="checking active player"),
    session: AsyncSession = Depends(get_db),
):
    try:
        user = await check_player_tg_id(session, tg_id)
        return await archive_game(session, id, user.id)

    except ApplicationException as e:
        raise HTTPException(status_code=e.code, detail=e.name)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__} - {e}")


@game_router.post("/games/{id}/restore", response_model=BaseShortResponse)
async def restore_game_router(
    id: int,
    tg_id: int = Query(description="checking active player"),
    session: AsyncSession = Depends(get_db),
):
    try:
        user = await check_player_tg_id(session, tg_id)
        return await restore_game(session, id, user.id)

    except ApplicationException as e:
        raise HTTPException(status_code=e.code, detail=e.name)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__} - {e}")


@game_router.post("/games/{game_id}/join", response_model=ResultResponse)
async def join_game_router(
    game_id: int,
    tg_id: int = Query(description="checking active player"),
    session: AsyncSession = Depends(get_db),
):
    try:
        player = await check_player_tg_id(session, tg_id)
        return await join_game(session, game_id, player.id)

    except ApplicationException as e:
        raise HTTPException(status_code=e.code, detail=e.name)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__} - {e}")


@game_router.post("/games/{game_id}/leave", response_model=ResultResponse)
async def leave_game_router(
    game_id: int,
    player_id: int | None = Query(default=None),
    tg_id: int = Query(description="checking active player"),
    session: AsyncSession = Depends(get_db),
):
    try:
        player = await check_player_tg_id(session, tg_id)
        if player_id:
            return await leave_game(session, game_id, player_id)
        
        return await leave_game(session, game_id, player.id)

    except ApplicationException as e:
        raise HTTPException(status_code=e.code, detail=e.name)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__} - {e}")


@game_router.post("/games/{id}/distribute-tables", response_model=DistributeTablesResponse)
async def distribute_tables_router(
    id: int,
    tg_id: int = Query(description="checking active player"),
    session: AsyncSession = Depends(get_db_manual),
):
    try:
        user = await check_player_tg_id(session, tg_id)
        return await distribute_tables(session, id, user.id)

    except ApplicationException as e:
        raise HTTPException(status_code=e.code, detail=e.name)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__} - {e}")
