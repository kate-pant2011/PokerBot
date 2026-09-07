# Текущая модель данных

**Статус:** Current **Проверено на commit:** `ed5ce0617dc8ebfee4f7a396153a4a813647cf79`

## Сущности

| ORM-модель | Назначение | Важные поля |
|---|---|---|
| `Player` | Профиль участника | `name`, `telegram_id`, `elo`, `elo_change_per_match`, `is_archived` |
| `Game` | Игра/турнир | `name`, `start_time`, `status`, `organizer_id`, Telegram poll/chat fields, `registered` |
| `GamePlayer` | Участие в игре | `game_id`, `player_id`, `status=joined/left` |
| `Table` | Стол игры | `game_id`, `number`, `started_at`, `finished_at` |
| `TablePlayer` | Период участия за столом | `player_id`, `table_id`, `is_active`, `position`, `chips`, `eliminated_by_id` |
| `EloHistory` | Запись изменения рейтинга | ссылки на игрока, игру и стол; рейтинг до/после, изменение, место и бонусы |
| `TelegramChat` | Привязка Telegram chat/topic | `chat_id`, `thread_id`, `activator_id`, опубликованная рассадка |

## Связи

```text
Player 1--* Game (organizer)
Player *--* Game (through GamePlayer)
Game   1--* Table
Player *--* Table (through TablePlayer)
Player 1--* EloHistory *--1 Game
TelegramChat 1--* Game
```

## Замечания к миграции

- `Season`, итог вечернего турнира и явная запись порядка выбывания отсутствуют.
- `TablePlayer.position` сейчас относится к моменту выбытия из единственного реального стола, а не гарантированно к итоговому месту во всём турнире.
- `Player.elo` и `EloHistory` нельзя автоматически считать сезонными очками: семантика и момент начисления различаются.
- ORM-модели и исторические миграции расходятся по части ограничений. Перед новой миграцией нужно сравнить Alembic head с фактической production-схемой.
- Legacy-поля нельзя удалять в первой миграции: сначала нужны новые таблицы, backfill и проверка результатов.
