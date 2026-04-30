from app.bot.utils.formatting import format_table_result


async def broadcast_table_results(bot, result: dict):
    text = format_table_result(result)

    for r in result["elo_history"]:
        tg_id = r["player"].get("telegram_id")

        if not tg_id:
            continue

        try:
            await bot.send_message(tg_id, text)
        except Exception:
            pass
