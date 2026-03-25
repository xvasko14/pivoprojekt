import os
import sqlite3
import uuid
from datetime import datetime, date, timezone


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
    now = datetime.now(timezone.utc).isoformat()
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
            """
            SELECT e.*, COUNT(CASE WHEN r.going = 1 THEN 1 END) as going_count
            FROM events e
            LEFT JOIN rsvps r ON r.event_id = e.id
            GROUP BY e.id
            ORDER BY e.event_date ASC, e.event_time ASC
            """
        ).fetchall()
        name_rows = conn.execute(
            "SELECT event_id, name FROM rsvps WHERE going = 1 ORDER BY created_at ASC"
        ).fetchall()

    names_by_event: dict[str, list[str]] = {}
    for row in name_rows:
        names_by_event.setdefault(row["event_id"], []).append(row["name"])

    all_events = []
    for r in rows:
        e = dict(r)
        e["going_names"] = names_by_event.get(e["id"], [])
        all_events.append(e)

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
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO rsvps (event_id, name, going, created_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(event_id, name) DO UPDATE SET going = excluded.going, created_at = excluded.created_at",
            (event_id, name, int(going), now),
        )


def update_event(event_id: str, place: str, event_date: str, event_time: str, description: str | None) -> bool:
    """Update event fields. Returns True if found and updated."""
    with get_connection() as conn:
        result = conn.execute(
            "UPDATE events SET place=?, event_date=?, event_time=?, description=? WHERE id=?",
            (place, event_date, event_time, description, event_id),
        )
    return result.rowcount == 1


def delete_event(event_id: str, token: str) -> bool:
    """Returns True if deleted, False if token mismatch or event not found."""
    with get_connection() as conn:
        result = conn.execute(
            "DELETE FROM events WHERE id = ? AND delete_token = ?",
            (event_id, token),
        )
    return result.rowcount == 1


def delete_event_by_id(event_id: str) -> bool:
    """Delete event by ID only, no token check. Returns True if deleted."""
    with get_connection() as conn:
        result = conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
    return result.rowcount == 1
