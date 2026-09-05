"""
Minimal username/password auth.

- Passwords are hashed with PBKDF2 (hashlib, standard library, no extra
  dependency) plus a random per-user salt. Never store plain passwords.
- Sessions are random tokens kept in memory (a plain dict), mapped to a
  username. This means everyone gets logged out on server restart, which
  is a reasonable tradeoff for a project this size; move `sessions` into
  the database (like game_state) if you want logins to survive restarts.
"""

import hashlib
import secrets

import db


def hash_password(password: str, salt: str = None) -> tuple[str, str]:
    """Return (password_hash, salt). Generates a new salt if none given."""
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return digest.hex(), salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    check_hash, _ = hash_password(password, salt)
    # constant-time comparison so response timing can't leak the hash
    return secrets.compare_digest(check_hash, password_hash)


def register_user(username: str, password: str) -> bool:
    """Return True on success, False if the username is already taken."""
    if db.get_user(username) is not None:
        return False
    password_hash, salt = hash_password(password)
    db.create_user(username, password_hash, salt)
    return True


def authenticate(username: str, password: str) -> bool:
    user = db.get_user(username)
    if user is None:
        return False
    return verify_password(password, user["password_hash"], user["salt"])


# session_token -> username
sessions = {}


def create_session(username: str) -> str:
    token = secrets.token_urlsafe(32)
    sessions[token] = username
    return token


def get_username(token: str) -> str:
    if token is None:
        return None
    return sessions.get(token)


def destroy_session(token: str):
    if token is not None:
        sessions.pop(token, None)