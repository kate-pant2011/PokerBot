from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.config import ApplicationException
from app.config.connection import get_db
from app.schemas.table_player import TablePlayerResponse, TablePlayerPatch, TablePlayerKnockout
from app.schemas.common import ResultResponse
from app.services.player import check_player_tg_id
from app.services.table_player import (
    get_table_players,
    add_player_at_table,
    change_table_player,
    leave_table,
)

table_player_router = APIRouter()


@table_player_router.get("/tables/{table_id}/players", response_model=list[TablePlayerResponse])
async def get_table_players_router(
    table_id: int,
    tg_id: int = Query(description="checking active player"),
    session: AsyncSession = Depends(get_db),
):
    try:
        await check_player_tg_id(session, tg_id)
        return await get_table_players(session, table_id)

    except ApplicationException as e:
        raise HTTPException(status_code=e.code, detail={"message": e.name, "payload": e.payload})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f" {type(e).__name__} - {e}")


@table_player_router.post("/tables/{table_id}/players", response_model=ResultResponse)
async def add_player_at_table_player_router(
    table_id: int,
    tg_id: int = Query(description="checking active player"),
    session: AsyncSession = Depends(get_db),
):
    try:
        user = await check_player_tg_id(session, tg_id)
        return await add_player_at_table(session=session, table_id=table_id, player_id=user.id)

    except ApplicationException as e:
        raise HTTPException(status_code=e.code, detail={"message": e.name, "payload": e.payload})

    except Exception as e:
        print(f"ERRRRORRRR {e}")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__} - {e}")


@table_player_router.patch(
    "/tables/{table_id}/players/{player_id}", response_model=TablePlayerResponse
)
async def change_table_player_router(
    table_id: int,
    player_id: int,
    item: TablePlayerPatch,
    tg_id: int = Query(description="checking active player"),
    session: AsyncSession = Depends(get_db),
):
    try:
        user = await check_player_tg_id(session, tg_id)
        
        return await change_table_player(session, item, table_id, user.id, player_id)

    except ApplicationException as e:
        raise HTTPException(status_code=e.code, detail={"message": e.name, "payload": e.payload})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f" {type(e).__name__} - {e}")


@table_player_router.post(
    "/tables/{table_id}/players/{player_id}/finish", response_model=TablePlayerKnockout
)
async def leave_table_router(
    table_id: int,
    player_id: int,
    item: TablePlayerPatch,
    tg_id: int = Query(description="checking active player"),
    session: AsyncSession = Depends(get_db),
):
    try:
        user = await check_player_tg_id(session, tg_id)
        return await leave_table(session, item, table_id, user.id, player_id, user.name)

    except ApplicationException as e:
        raise HTTPException(status_code=e.code, detail={"message": e.name, "payload": e.payload})

    except Exception as e:
        print(f"ERROR {e}")
        raise HTTPException(status_code=500, detail=f" {type(e).__name__} - {e}")
