"""
Minimal SQLite persistence for the checkers game.

Uses the standard library sqlite3 module, so there's nothing extra to
install. Tables:

- users: username + password hash, for login.
- game_state: a single row holding the current game as JSON (reusing
  GameState.toDict()/loadFromDict(), which already existed for your
  file-based save/load).
- moves: an append-only log of every move applied, tagged with who made
  it, for a simple history view.
"""

import json
import sqlite3
from datetime import datetime, timezone

DB_PATH = "checkers.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS game_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            state_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS moves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player INTEGER NOT NULL,
            username TEXT,
            from_pos TEXT NOT NULL,
            to_pos TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    # If moves already exists from before auth was added, add the new
    # column rather than requiring you to delete the database.
    try:
        conn.execute("ALTER TABLE moves ADD COLUMN username TEXT")
    except sqlite3.OperationalError:
        pass  # column already exists
    conn.commit()
    conn.close()


def create_user(username, password_hash, salt):
    conn = get_connection()
    conn.execute("""
        INSERT INTO users (username, password_hash, salt, created_at)
        VALUES (?, ?, ?, ?)
    """, (username, password_hash, salt, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()


def get_user(username):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def load_game_state():
    """Return the saved state dict, or None if there isn't one yet."""
    conn = get_connection()
    row = conn.execute("SELECT state_json FROM game_state WHERE id = 1").fetchone()
    conn.close()
    if row is None:
        return None
    return json.loads(row["state_json"])


def save_game_state(state_dict):
    """Upsert the single shared game's state. id is pinned to 1 since
    there's only ever one game running at a time."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO game_state (id, state_json, updated_at)
        VALUES (1, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            state_json = excluded.state_json,
            updated_at = excluded.updated_at
    """, (json.dumps(state_dict), datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()


def log_move(player, from_pos, to_pos, username=None):
    conn = get_connection()
    conn.execute("""
        INSERT INTO moves (player, username, from_pos, to_pos, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        player,
        username,
        f"{from_pos[0]},{from_pos[1]}",
        f"{to_pos[0]},{to_pos[1]}",
        datetime.now(timezone.utc).isoformat(),
    ))
    conn.commit()
    conn.close()


def get_move_history(limit=50):
    conn = get_connection()
    rows = conn.execute("""
        SELECT player, username, from_pos, to_pos, created_at
        FROM moves ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]