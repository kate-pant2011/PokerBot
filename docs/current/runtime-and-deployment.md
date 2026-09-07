# Запуск и production-контур

**Статус:** частично Current, требует сверки с сервером **Проверено на commit:** `ed5ce0617dc8ebfee4f7a396153a4a813647cf79`

## Что подтверждено репозиторием

- Приложение рассчитано на Python 3.12, FastAPI, aiogram, PostgreSQL, SQLAlchemy/asyncpg и Alembic.
- Dockerfile запускает `uvicorn app.main:app` на порту 8000.
- Nginx-конфигурация проксирует HTTP на сервис `backend:8000`.
- При старте приложения Telegram webhook устанавливается на `{BASE_URL}/webhook`.

## Чего нет в Git

- `app/config/config.py` с настройками и `ApplicationException`;
- `app/config/connection.py` с engine, session factory и `get_db`;
- `docker-compose.yml`, хотя README предлагает его запуск;
- пример `.env` с безопасными заглушками;
- CI, healthcheck, backup/restore runbook и observability-конфигурация.

Без этих файлов clean clone не импортирует `app.main`. Секреты добавлять в Git нельзя; нужны шаблон конфигурации и документированный способ их передачи.

## Что проверить на production до изменения поведения

- deployed commit/image и способ доставки релиза;
- точные имена переменных окружения без публикации их значений;
- фактический Alembic revision и отличия схемы БД;
- кто завершает TLS и какие маршруты доступны из интернета;
- наличие других клиентов REST API;
- политика backup/restore и время последней проверенной реставрации;
- логи, метрики и оповещения;
- допустимое окно обслуживания и сценарий быстрого отката.

Результат этой инвентаризации должен обновить документ до первой production- миграции.
