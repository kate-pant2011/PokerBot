from app.database.tgchat import get_all_tgchats, get_tgchat_by_chat_id, add_tgchat
from app.config.config import ApplicationException
from app.schemas.common import to_schema
from app.schemas.tgchat import TgchatShortResponse, TgchatListResponse
from app.schemas.common import ResultResponse

async def get_tgchat_list(session, limit, offset):
    tgchats = await get_all_tgchats(session, limit, offset)

    return TgchatListResponse(
        items=tgchats.items,
        total=tgchats.total,
        limit=limit,
        offset=offset,
    )

async def get_tgchat_id(session, chat_id):
    tgchat = await get_tgchat_by_chat_id(session, chat_id)

    if not tgchat:
        raise ApplicationException("tgchat Not found", 404)
    
    return to_schema(TgchatShortResponse, tgchat)


async def create_tgchat(session, item, user_id):

    tgchat = await get_tgchat_by_chat_id(session, item.chat_id)

    if tgchat:
        raise ApplicationException("tgchat already exists", 400)

    new_tgchat = await add_tgchat(session, item, user_id)

    return ResultResponse(result="added")