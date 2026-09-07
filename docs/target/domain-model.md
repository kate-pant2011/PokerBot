# Целевая доменная модель

**Статус:** Accepted на уровне понятий; физическая схема БД проектируется отдельно

## Агрегаты и сущности

### `Season`

- `id`, `name`, `starts_at`, `ends_at`, `status`;
- содержит несколько `EveningTournament`;
- публикует таблицу как сумму зафиксированных `TournamentResult.points`.

### `EveningTournament`

- `id`, `season_id`, `name`, `scheduled_at`, `started_at`, `finished_at`;
- `status`: `draft`, `registration`, `running`, `finished`, `canceled`;
- `physical_table_limit` и конфигурация поздней регистрации;
- организатор и Telegram-контекст.

### `TournamentParticipant`

Связывает `Player` и `EveningTournament` и хранит турнирное состояние:

- `status`: `registered`, `arrived`, `waiting`, `seated`, `eliminated`, `withdrawn`, `finished`;
- `arrived_at`, `seated_at`, `eliminated_at`;
- итоговое `place`, которое появляется только при финализации результатов.

Статус `eliminated` терминален для участия в freezeout-турнире.

### `TournamentTable` и `SeatAssignment`

`TournamentTable` — реальный стол конкретного турнира с уникальным номером и состоянием `open/closed`. `SeatAssignment` — интервал, в течение которого игрок сидел за столом: `assigned_at`, `released_at`, причина назначения/перемещения. История нужна для объяснимости шафла; активным может быть не более одного назначения участника.

### `LateArrivalBatch`

Сохранённая группа ожидающих опоздавших: `opened_at`, `deadline_at`, `status` и состав. Таймер должен переживать рестарт процесса; одного in-memory task недостаточно.

### `Elimination`

Неизменяемый факт выбытия: `participant_id`, `sequence`, `occurred_at`, `recorded_at`, `recorded_by`, `source`. Поля `eliminated_by` нет. `sequence` однозначно задаёт порядок и защищён уникальным ограничением внутри турнира.

### `TournamentResult`

Неизменяемый опубликованный результат: `participant_id`, `place`, `points`, `scoring_version`, `published_at`. Для пары турнир–участник допускается ровно один актуальный результат; исправление должно быть отдельной аудируемой операцией.

## Ключевые инварианты

- У игрока не более одного участия в одном турнире.
- Выбывший участник не может снова стать ожидающим или посаженным.
- Посаженный участник имеет ровно одно активное назначение стола.
- Открытых столов не больше `physical_table_limit`.
- Место уникально внутри завершённого турнира, если отдельно не принято правило ничьих.
- Результаты создаются атомарно для всего турнира и не начисляются повторно.
- Сезонный рейтинг выводится из результатов, а не поддерживается независимым изменяемым счётчиком.

## Сопоставление с legacy

| Legacy | Цель |
|---|---|
| `Game` | `EveningTournament` плюс ссылка на `Season` |
| `GamePlayer` | `TournamentParticipant` |
| `Table` | `TournamentTable` |
| `TablePlayer` | `SeatAssignment`; выбытие вынесено отдельно |
| `Player.elo`, `EloHistory` | вычисляемый сезонный рейтинг и `TournamentResult` |
| `eliminated_by_id` | не переносится в целевую семантику |

Это логическое соответствие, не инструкция переименовывать legacy-таблицы на месте.
