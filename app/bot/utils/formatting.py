def leaderboard_text(players: list[dict]) -> str:
    if not players:
        return "Leaderboard is empty"

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}

    lines = ["<b>🏆 Leaderboard</b>\n"]

    for i, p in enumerate(players, 1):
        medal = medals.get(i, f"{i}.")
        lines.append(f"{medal} <b>{p['name']}</b> — <code>{int(p['elo'])}</code>")

    return "\n".join(lines)


def format_table_result(result: dict) -> str:
    text = f"🏁 Table {result['number']} finished\n\n"

    for r in result["elo_history"]:
        change = r["elo_change"] + r["bounty_bonus"]
        sign = "+" if change >= 0 else ""

        text += (
            f"{r['position']}. {r['player']['name']} — "
            f"{r['chips']} chips | "
            f"{sign}{round(change, 1)}\n"
        )

    return text
