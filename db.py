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

    existing_cols = [
        row["name"] for row in conn.execute("PRAGMA table_info(game_state)").fetchall()
    ]
    if existing_cols and "username" not in existing_cols:
        conn.execute("DROP TABLE game_state")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS game_state (
            username TEXT PRIMARY KEY,
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


def load_game_state(username):
    """Return that account's saved state dict, or None if it doesn't have one yet."""
    conn = get_connection()
    row = conn.execute(
        "SELECT state_json FROM game_state WHERE username = ?", (username,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return json.loads(row["state_json"])


def save_game_state(username, state_dict):
    """Upsert this account's game state."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO game_state (username, state_json, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(username) DO UPDATE SET
            state_json = excluded.state_json,
            updated_at = excluded.updated_at
    """, (username, json.dumps(state_dict), datetime.now(timezone.utc).isoformat()))
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


def get_move_history(username, limit=50):
    """This account's own move history only."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT player, username, from_pos, to_pos, created_at
        FROM moves WHERE username = ? ORDER BY id DESC LIMIT ?
    """, (username, limit)).fetchall()
    conn.close()
    return [dict(row) for row in rows]