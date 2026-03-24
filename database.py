import os
import sqlite3
import uuid
from datetime import datetime, date


def get_connection():
    path = os.getenv("DATABASE_PATH", "pivo.db")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_tables():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                place TEXT NOT NULL,
                event_date TEXT NOT NULL,
                event_time TEXT NOT NULL,
                description TEXT,
                delete_token TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rsvps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                going INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(event_id, name)
            )
        """)


def create_event(place: str, event_date: str, event_time: str, description: str | None) -> dict:
    event_id = str(uuid.uuid4())
    delete_token = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO events (id, place, event_date, event_time, description, delete_token, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (event_id, place, event_date, event_time, description, delete_token, now),
        )
    return {"id": event_id, "delete_token": delete_token}


def get_event(event_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    return dict(row) if row else None


def get_all_events() -> tuple[list[dict], list[dict]]:
    """Returns (upcoming, past) split by today's date."""
    today = date.today().isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM events ORDER BY event_date ASC, event_time ASC"
        ).fetchall()
    all_events = [dict(r) for r in rows]
    upcoming = [e for e in all_events if e["event_date"] >= today]
    past = [e for e in all_events if e["event_date"] < today]
    return upcoming, past


def get_rsvps(event_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM rsvps WHERE event_id = ? ORDER BY created_at ASC",
            (event_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def upsert_rsvp(event_id: str, name: str, going: bool) -> None:
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO rsvps (event_id, name, going, created_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(event_id, name) DO UPDATE SET going = excluded.going, created_at = excluded.created_at",
            (event_id, name, int(going), now),
        )


def delete_event(event_id: str, token: str) -> bool:
    """Returns True if deleted, False if token mismatch or event not found."""
    event = get_event(event_id)
    if not event or event["delete_token"] != token:
        return False
    with get_connection() as conn:
        conn.execute("DELETE FROM rsvps WHERE event_id = ?", (event_id,))
        conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
    return True
