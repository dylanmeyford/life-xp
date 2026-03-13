"""SQLite database setup and connection management."""

import sqlite3
import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("LIFE_XP_DATA", Path.home() / ".life-xp"))
DB_PATH = DATA_DIR / "life.db"


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    icon TEXT NOT NULL DEFAULT '⭐',
    color TEXT NOT NULL DEFAULT 'white'
);

CREATE TABLE IF NOT EXISTS goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    category_id INTEGER REFERENCES categories(id),
    parent_id INTEGER REFERENCES goals(id),
    xp_reward INTEGER NOT NULL DEFAULT 100,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK(status IN ('active', 'completed', 'abandoned', 'paused')),
    target_value REAL,
    current_value REAL DEFAULT 0,
    unit TEXT,
    due_date TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS habits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    category_id INTEGER REFERENCES categories(id),
    frequency TEXT NOT NULL DEFAULT 'daily'
        CHECK(frequency IN ('daily', 'weekly', 'monthly')),
    xp_per_check INTEGER NOT NULL DEFAULT 25,
    streak_bonus_multiplier REAL NOT NULL DEFAULT 0.1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS habit_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    habit_id INTEGER NOT NULL REFERENCES habits(id),
    checked_date TEXT NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(habit_id, checked_date)
);

CREATE TABLE IF NOT EXISTS xp_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    amount INTEGER NOT NULL,
    source_type TEXT NOT NULL
        CHECK(source_type IN ('goal', 'habit', 'quest', 'bonus', 'streak')),
    source_id INTEGER,
    description TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS quests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    category_id INTEGER REFERENCES categories(id),
    xp_reward INTEGER NOT NULL DEFAULT 500,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK(status IN ('active', 'completed', 'failed', 'expired')),
    deadline TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS quest_objectives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quest_id INTEGER NOT NULL REFERENCES quests(id),
    goal_id INTEGER REFERENCES goals(id),
    description TEXT NOT NULL,
    completed INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS rewards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    xp_cost INTEGER NOT NULL,
    redeemed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sensor_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sensor_type TEXT NOT NULL,
    goal_id INTEGER REFERENCES goals(id),
    habit_id INTEGER REFERENCES habits(id),
    config_json TEXT NOT NULL DEFAULT '{}',
    enabled INTEGER NOT NULL DEFAULT 1,
    last_checked TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    processed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Seed default categories
INSERT OR IGNORE INTO categories (name, icon, color) VALUES
    ('Fitness', '💪', 'green'),
    ('Finance', '💰', 'yellow'),
    ('Social', '🤝', 'cyan'),
    ('Learning', '📚', 'blue'),
    ('Productivity', '⚡', 'magenta'),
    ('Creative', '🎨', 'red'),
    ('Health', '❤️', 'green'),
    ('Mindfulness', '🧘', 'cyan');
""";
