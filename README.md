# Poker Tournaments Management System

Backend-system for local poker club

The project includes:
- Telegram bot as the main user interface
- FastAPI REST API
- player management system
- rating system
- Telegram chats/topics integration
- webhook infrastructure via Nginx

---
# Stack

- Aiogram
- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- asyncpg
- Docker Compose
- Nginx (webhook)
- Ubuntu Server

---

# Architecture

The project uses layer-based architecture.

```bash
project/
├── app/
│   ├── bot/          # Telegram bot logic
│   │   ├── handlers/
│   │   ├── states/
│   │   ├── utils/
│   ├── config/
│   ├── database/
│   ├── models/       # SQLAlchemy models
│   ├── routers/      # FastAPI endpoints 
│   ├── schemas/      # Pydantic schemas
│   ├── services/     # Business logic
│   ├── main.py       # Application entry point 
├── README.md
└── requirements.txt
```

# Core Entities

## Player
A participant of the poker club.

Includes:
- Telegram ID
- current rating
- rating history
- table participation history

## Game
A poker tournament/event.

Includes:
- organizer
- players
- tables
- Telegram chat integration
- rating history

## Table
A game table.

Includes:
- multiple rounds
- table participants
- player positions
- eliminations

## TablePlayer
Represents a player’s state and actions at a table.

Includes:
- chips
- position
- elimination data
- active state
- timestamps

## EloHistory
Stores rating changes over time.

Includes:
- rating before/after
- rating change
- bonuses
- position
- chips

## TelegramChat
Telegram chat/topic integration for games


# Infrastructure

The project is deployed using Docker Compose on an Ubuntu Server.

Components:
- backend container
- PostgreSQL database
- Nginx reverse proxy
- Telegram webhook integration

---

# Run

```bash
docker compose up --build -d
```

---

# Project Status

The project is currently in active development.

Planned features:
- improved rating system
- admin panel 

---

# Credits

Rating system author: https://github.com/Prost444

The initial version of the project also belongs to the same author and was later forked and refactored.

