"""SQLite database layer for Life XP."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import aiosqlite

DATA_DIR = Path(os.environ.get("LIFE_XP_DATA", Path.home() / ".life-xp"))
DB_PATH = DATA_DIR / "life.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS goals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    description TEXT,
    target      TEXT,           -- e.g. "80 kg", "$10000"
    category    TEXT,           -- e.g. "health", "finance", "learning"
    status      TEXT DEFAULT 'active',  -- active | completed | archived
    xp_reward   INTEGER DEFAULT 500,
    created_at  TEXT DEFAULT (datetime('now')),
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS sub_goals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id     INTEGER NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    description TEXT,
    target      TEXT,
    status      TEXT DEFAULT 'pending',  -- pending | active | completed
    xp_reward   INTEGER DEFAULT 50,
    sort_order  INTEGER DEFAULT 0,
    created_at  TEXT DEFAULT (datetime('now')),
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS sensor_configs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id     INTEGER NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
    sensor_type TEXT NOT NULL,        -- e.g. "swift_health", "api", "cli", "browser"
    config      TEXT DEFAULT '{}',    -- JSON config blob
    status      TEXT DEFAULT 'pending',  -- pending | testing | active | failed
    last_run    TEXT,
    last_value  TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS xp_ledger (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    amount      INTEGER NOT NULL,
    source_type TEXT NOT NULL,        -- goal | sub_goal | streak | bonus
    source_id   INTEGER,
    reason      TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sensor_readings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sensor_id   INTEGER NOT NULL REFERENCES sensor_configs(id) ON DELETE CASCADE,
    value       TEXT NOT NULL,
    raw_data    TEXT,                 -- JSON blob of full reading
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS agent_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id     INTEGER REFERENCES goals(id) ON DELETE SET NULL,
    role        TEXT NOT NULL,        -- user | assistant | system | tool
    content     TEXT NOT NULL,
    tool_use    TEXT,                 -- JSON if this is a tool call/result
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL
);
"""


async def get_db() -> aiosqlite.Connection:
    """Get a database connection, creating the schema if needed."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.executescript(SCHEMA)
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


# ── Convenience helpers ──────────────────────────────────────────────

async def insert(db: aiosqlite.Connection, table: str, data: dict) -> int:
    cols = ", ".join(data.keys())
    placeholders = ", ".join("?" for _ in data)
    cur = await db.execute(
        f"INSERT INTO {table} ({cols}) VALUES ({placeholders})",
        list(data.values()),
    )
    await db.commit()
    return cur.lastrowid


async def fetch_all(db: aiosqlite.Connection, query: str, params=()) -> list[dict]:
    cur = await db.execute(query, params)
    rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def fetch_one(db: aiosqlite.Connection, query: str, params=()) -> dict | None:
    cur = await db.execute(query, params)
    row = await cur.fetchone()
    return dict(row) if row else None


async def update(db: aiosqlite.Connection, table: str, row_id: int, data: dict):
    sets = ", ".join(f"{k} = ?" for k in data)
    await db.execute(
        f"UPDATE {table} SET {sets} WHERE id = ?",
        [*data.values(), row_id],
    )
    await db.commit()
