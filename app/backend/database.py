"""Small SQLite persistence layer for local accounts and per-user providers."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False)


def _database_path() -> Path:
    configured = os.getenv("AUTH_DB_PATH", "").strip()
    if not configured:
        return PROJECT_ROOT / "data" / "app.db"
    path = Path(configured).expanduser()
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


DB_PATH = _database_path()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                display_name TEXT NOT NULL,
                avatar_data TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS providers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                provider_type TEXT NOT NULL,
                protocol TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                api_key_encrypted TEXT NOT NULL,
                model TEXT NOT NULL,
                api_version TEXT,
                reasoning_effort TEXT NOT NULL DEFAULT 'auto',
                available_models TEXT NOT NULL DEFAULT '[]',
                active INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_providers_user ON providers(user_id, updated_at DESC);
            CREATE TABLE IF NOT EXISTS attachments (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                kind TEXT NOT NULL,
                storage_path TEXT NOT NULL,
                extracted_text TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_attachments_user ON attachments(user_id, created_at DESC);
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                thread_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_conversation_messages_thread
                ON conversation_messages(user_id, thread_id, id);
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                thread_id TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '新对话',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, thread_id)
            );
            CREATE INDEX IF NOT EXISTS idx_conversations_user_updated
                ON conversations(user_id, updated_at DESC);
            """
        )
        # Keep existing local databases compatible with the profile feature.
        columns = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "avatar_data" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN avatar_data TEXT NOT NULL DEFAULT ''")
        provider_columns = {row[1] for row in conn.execute("PRAGMA table_info(providers)").fetchall()}
        if "reasoning_effort" not in provider_columns:
            conn.execute("ALTER TABLE providers ADD COLUMN reasoning_effort TEXT NOT NULL DEFAULT 'auto'")
        if "available_models" not in provider_columns:
            conn.execute("ALTER TABLE providers ADD COLUMN available_models TEXT NOT NULL DEFAULT '[]'")


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
