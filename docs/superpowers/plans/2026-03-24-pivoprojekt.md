# PivoProjekt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a no-login web app where anyone can create beer outing events and RSVP with their name.

**Architecture:** FastAPI serves server-side-rendered Jinja2 HTML templates. All data lives in a single SQLite file (`pivo.db`). Sessions (via Starlette `SessionMiddleware`) are used only for one-time flash messages. No JavaScript framework.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, Jinja2, SQLite (stdlib `sqlite3`), python-multipart, itsdangerous, pytest, httpx

---

## File Structure

```
PivoProjekt/
├── main.py                          # FastAPI app + all route handlers
├── database.py                      # SQLite connection + all CRUD functions
├── templates/
│   ├── base.html                    # Base layout: nav bar, flash message slot
│   ├── home.html                    # Home: upcoming event cards + history list
│   ├── event_detail.html            # Event detail + RSVP summary + RSVP form
│   ├── event_new.html               # Create event form
│   ├── event_delete_confirm.html    # Delete confirmation page
│   ├── 404.html                     # Not found error page
│   └── 403.html                     # Forbidden error page
├── static/
│   └── style.css                    # All styles (nav, cards, forms, flash)
├── tests/
│   ├── conftest.py                  # pytest fixtures: TestClient + per-test SQLite DB
│   ├── test_home.py                 # Tests for GET /
│   ├── test_events.py               # Tests for create event, event detail, delete flow
│   └── test_rsvp.py                 # Tests for POST /events/{id}/rsvp (upsert)
├── requirements.txt
└── .gitignore
```

---

## Task 1: Project Setup

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`

- [ ] **Step 1: Create requirements.txt**

```
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
jinja2>=3.1.0
python-multipart>=0.0.12
itsdangerous>=2.2.0
pytest>=8.0.0
httpx>=0.27.0
```

- [ ] **Step 2: Create .gitignore**

```
__pycache__/
*.pyc
*.pyo
.pytest_cache/
*.db
.env
.venv/
venv/
```

- [ ] **Step 3: Install dependencies**

```bash
pip install -r requirements.txt
```

- [ ] **Step 4: Create directory structure**

```bash
mkdir -p templates static tests
touch tests/__init__.py
```

- [ ] **Step 5: Commit**

> Note: git repo and remote (git@gitlab.com:xvasko14/pivoproject.git) are already initialised. Skip `git init` / `git remote add`.

```bash
git add requirements.txt .gitignore
git commit -m "chore: project setup — requirements and gitignore"
```

---

## Task 2: Database Layer

**Files:**
- Create: `database.py`
- Create: `tests/conftest.py`

The database module reads the DB path from `DATABASE_PATH` env var on every connection call so tests can override it without module reimport.

- [ ] **Step 1: Create database.py with connection and table creation**

```python
# database.py
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
```

- [ ] **Step 2: Create tests/conftest.py**

```python
# tests/conftest.py
import os
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def test_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DATABASE_PATH", db_path)
    import database
    database.create_tables()
    yield db_path


@pytest.fixture
def client(test_db):
    import importlib
    import main
    importlib.reload(main)
    from main import app
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture
def sample_event():
    import database
    return database.create_event(
        place="Hostinec U Karla",
        event_date="2099-12-31",
        event_time="19:00",
        description="Testovaci event",
    )
```

- [ ] **Step 3: Write database tests**

Create `tests/test_db.py` (temporary, just to verify DB layer works):

```python
# tests/test_db.py
import database


def test_create_and_get_event():
    result = database.create_event("U Karla", "2099-12-31", "19:00", "Test")
    event = database.get_event(result["id"])
    assert event is not None
    assert event["place"] == "U Karla"
    assert event["delete_token"] == result["delete_token"]


def test_get_event_not_found():
    assert database.get_event("nonexistent-id") is None


def test_upsert_rsvp_going():
    ev = database.create_event("Pub", "2099-01-01", "18:00", None)
    database.upsert_rsvp(ev["id"], "Marek", True)
    rsvps = database.get_rsvps(ev["id"])
    assert len(rsvps) == 1
    assert rsvps[0]["name"] == "Marek"
    assert rsvps[0]["going"] == 1


def test_upsert_rsvp_overwrites():
    ev = database.create_event("Pub", "2099-01-01", "18:00", None)
    database.upsert_rsvp(ev["id"], "Marek", True)
    database.upsert_rsvp(ev["id"], "Marek", False)
    rsvps = database.get_rsvps(ev["id"])
    assert len(rsvps) == 1
    assert rsvps[0]["going"] == 0


def test_delete_event_valid_token():
    ev = database.create_event("Pub", "2099-01-01", "18:00", None)
    database.upsert_rsvp(ev["id"], "Jano", True)
    ok = database.delete_event(ev["id"], ev["delete_token"])
    assert ok is True
    assert database.get_event(ev["id"]) is None
    assert database.get_rsvps(ev["id"]) == []


def test_delete_event_wrong_token():
    ev = database.create_event("Pub", "2099-01-01", "18:00", None)
    ok = database.delete_event(ev["id"], "wrong-token")
    assert ok is False
    assert database.get_event(ev["id"]) is not None


def test_get_all_events_split():
    database.create_event("Future Pub", "2099-12-31", "19:00", None)
    database.create_event("Past Pub", "2000-01-01", "19:00", None)
    upcoming, past = database.get_all_events()
    assert any(e["place"] == "Future Pub" for e in upcoming)
    assert any(e["place"] == "Past Pub" for e in past)
```

- [ ] **Step 4: Run database tests**

```bash
pytest tests/test_db.py -v
```

Expected: all 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add database.py tests/conftest.py tests/test_db.py tests/__init__.py
git commit -m "feat: database layer with CRUD operations and tests"
```

---

## Task 3: FastAPI App Skeleton

**Files:**
- Create: `main.py`

- [ ] **Step 1: Create main.py with app, middleware, and static/template setup**

```python
# main.py
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

import database

database.create_tables()

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="dev-secret-change-in-prod")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
```

- [ ] **Step 2: Verify app starts**

```bash
uvicorn main:app --reload
```

Expected: "Application startup complete." (Ctrl+C to stop)

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: FastAPI app skeleton with sessions and static files"
```

---

## Task 4: Base Template and CSS

**Files:**
- Create: `templates/base.html`
- Create: `static/style.css`

- [ ] **Step 1: Create base.html**

```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html lang="sk">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}PivoProjekt{% endblock %}</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <nav class="navbar">
    <a href="/" class="nav-brand">🍺 PivoProjekt</a>
    <a href="/events/new" class="btn btn-primary">+ Nový event</a>
  </nav>

  {% if flash %}
  <div class="flash flash-{{ flash.type }}">
    {{ flash.message | safe }}
  </div>
  {% endif %}

  <main class="container">
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

- [ ] **Step 2: Create static/style.css**

```css
/* static/style.css */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: system-ui, -apple-system, sans-serif;
  background: #f5f5f5;
  color: #222;
  line-height: 1.5;
}

/* Nav */
.navbar {
  background: #fff;
  border-bottom: 1px solid #e0e0e0;
  padding: 12px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.nav-brand { font-size: 1.2rem; font-weight: 700; text-decoration: none; color: #222; }

/* Buttons */
.btn {
  padding: 8px 16px;
  border-radius: 6px;
  text-decoration: none;
  font-size: 0.9rem;
  cursor: pointer;
  border: none;
  display: inline-block;
}
.btn-primary { background: #4f6ef7; color: #fff; }
.btn-primary:hover { background: #3a58d6; }
.btn-danger { background: #ef5350; color: #fff; }
.btn-danger:hover { background: #c62828; }
.btn-success { background: #4caf50; color: #fff; }
.btn-success:hover { background: #2e7d32; }
.btn-secondary { background: #e0e0e0; color: #333; }
.btn-secondary:hover { background: #bdbdbd; }

/* Container */
.container { max-width: 800px; margin: 32px auto; padding: 0 16px; }

/* Flash messages */
.flash {
  padding: 14px 24px;
  margin: 0;
  font-size: 0.95rem;
}
.flash-warning { background: #fff8e1; border-bottom: 2px solid #ffe082; }
.flash-success { background: #e8f5e9; border-bottom: 2px solid #a5d6a7; }
.flash-error   { background: #fce4e4; border-bottom: 2px solid #ef9a9a; }

/* Section headings */
.section-title {
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #888;
  margin-bottom: 12px;
}

/* Event cards (upcoming) */
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
  margin-bottom: 40px;
}
.card {
  background: #fff;
  border: 2px solid #c5cef9;
  border-radius: 10px;
  padding: 16px;
  text-decoration: none;
  color: inherit;
  display: block;
  transition: border-color 0.15s;
}
.card:hover { border-color: #4f6ef7; }
.card-place { font-weight: 700; font-size: 1rem; margin-bottom: 4px; }
.card-datetime { color: #666; font-size: 0.88rem; margin-bottom: 8px; }
.card-going { font-size: 0.85rem; }

/* History list */
.history-list { display: flex; flex-direction: column; gap: 8px; }
.history-item {
  background: #fafafa;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 10px 14px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  text-decoration: none;
  color: #999;
  font-size: 0.9rem;
}
.history-item:hover { background: #f0f0f0; color: #666; }

/* Event detail */
.event-header { margin-bottom: 24px; }
.event-title { font-size: 1.6rem; font-weight: 700; margin-bottom: 6px; }
.event-meta { color: #666; font-size: 0.95rem; margin-bottom: 4px; }
.event-desc { color: #555; font-size: 0.9rem; margin-top: 8px; }

.rsvp-summary { display: flex; gap: 16px; margin-bottom: 28px; }
.rsvp-box {
  flex: 1;
  border-radius: 10px;
  padding: 14px 16px;
}
.rsvp-box-going   { background: #e8f5e9; border: 1px solid #a5d6a7; }
.rsvp-box-not     { background: #fce4e4; border: 1px solid #ef9a9a; }
.rsvp-count { font-size: 1.8rem; font-weight: 700; }
.rsvp-label { font-size: 0.8rem; color: #555; margin-bottom: 6px; }
.rsvp-names { font-size: 0.82rem; color: #777; }

.rsvp-form {
  background: #f8f9ff;
  border: 1px solid #e0e4ff;
  border-radius: 10px;
  padding: 20px;
  margin-bottom: 16px;
}
.rsvp-form h3 { font-size: 1rem; margin-bottom: 14px; }
.rsvp-buttons { display: flex; gap: 10px; margin-top: 10px; }
.rsvp-buttons button { flex: 1; padding: 10px; font-size: 0.95rem; }

/* Forms */
.form-group { margin-bottom: 16px; }
.form-group label {
  display: block;
  font-size: 0.82rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #666;
  margin-bottom: 6px;
}
.form-group input, .form-group textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #ccc;
  border-radius: 6px;
  font-size: 0.95rem;
  font-family: inherit;
}
.form-group input:focus, .form-group textarea:focus {
  outline: none;
  border-color: #4f6ef7;
}
.form-row { display: flex; gap: 12px; }
.form-row .form-group { flex: 1; }
.form-error { color: #c62828; font-size: 0.85rem; margin-top: 4px; }

.back-link { display: inline-block; margin-bottom: 20px; color: #4f6ef7; text-decoration: none; font-size: 0.9rem; }
.back-link:hover { text-decoration: underline; }

.organizer-hint { font-size: 0.8rem; color: #bbb; text-align: center; margin-top: 12px; }

/* Delete confirm */
.danger-box {
  background: #fce4e4;
  border: 1px solid #ef9a9a;
  border-radius: 10px;
  padding: 24px;
  text-align: center;
}
.danger-box h2 { margin-bottom: 12px; }
.danger-box p { margin-bottom: 20px; color: #555; }
.danger-actions { display: flex; gap: 12px; justify-content: center; }

/* Error pages */
.error-page { text-align: center; padding: 60px 20px; }
.error-page h1 { font-size: 4rem; color: #e0e0e0; margin-bottom: 8px; }
.error-page p { color: #888; margin-bottom: 24px; }
```

- [ ] **Step 3: Commit**

```bash
git add templates/base.html static/style.css
git commit -m "feat: base template and CSS styles"
```

---

## Task 5: Home Page

**Files:**
- Modify: `main.py` — add GET `/` route
- Create: `templates/home.html`
- Create: `tests/test_home.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_home.py
def test_home_empty(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "PivoProjekt" in response.text


def test_home_shows_upcoming_event(client, sample_event):
    import database
    database.create_event("Future Pub", "2099-12-31", "19:00", None)
    response = client.get("/")
    assert response.status_code == 200
    assert "Future Pub" in response.text


def test_home_shows_history(client):
    import database
    database.create_event("Past Pub", "2000-01-01", "19:00", None)
    response = client.get("/")
    assert response.status_code == 200
    assert "Past Pub" in response.text
```

- [ ] **Step 2: Run tests to see them fail**

```bash
pytest tests/test_home.py -v
```

Expected: FAIL (route not defined yet)

- [ ] **Step 3: Add GET / route to main.py**

Add to `main.py`:

```python
from fastapi.responses import RedirectResponse
from fastapi import Form


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    flash = request.session.pop("flash", None)
    upcoming, past = database.get_all_events()
    return templates.TemplateResponse("home.html", {
        "request": request,
        "upcoming": upcoming,
        "past": past,
        "flash": flash,
    })
```

- [ ] **Step 4: Create templates/home.html**

```html
<!-- templates/home.html -->
{% extends "base.html" %}
{% block title %}PivoProjekt — Pivo s kamošmi{% endblock %}
{% block content %}

{% if upcoming %}
<p class="section-title">Nadchádzajúce</p>
<div class="cards">
  {% for event in upcoming %}
  <a href="/events/{{ event.id }}" class="card">
    <div class="card-place">🍺 {{ event.place }}</div>
    <div class="card-datetime">
      📅 {{ event.event_date }} o {{ event.event_time }}
    </div>
    <div class="card-going">✅ {{ event.going_count }} idú</div>
  </a>
  {% endfor %}
</div>
{% else %}
<p style="color:#aaa;margin-bottom:40px">Žiadne nadchádzajúce eventy. <a href="/events/new">Vytvor prvý!</a></p>
{% endif %}

{% if past %}
<p class="section-title">História</p>
<div class="history-list">
  {% for event in past %}
  <a href="/events/{{ event.id }}" class="history-item">
    <span>{{ event.place }}</span>
    <span>{{ event.event_date }} · ✅ {{ event.going_count }} išlo</span>
  </a>
  {% endfor %}
</div>
{% endif %}

{% endblock %}
```

- [ ] **Step 5: Add going_count to events in get_all_events**

Update `database.py` — `get_all_events()` needs to include a `going_count` for each event. Modify the function:

```python
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
    all_events = [dict(r) for r in rows]
    upcoming = [e for e in all_events if e["event_date"] >= today]
    past = [e for e in all_events if e["event_date"] < today]
    return upcoming, past
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_home.py tests/test_db.py -v
```

Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add main.py templates/home.html database.py tests/test_home.py
git commit -m "feat: home page with upcoming cards and history"
```

---

## Task 6: Create Event

**Files:**
- Modify: `main.py` — add GET/POST `/events/new`
- Create: `templates/event_new.html`
- Modify: `tests/test_events.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_events.py
def test_get_new_event_form(client):
    response = client.get("/events/new")
    assert response.status_code == 200
    assert "Nový event" in response.text


def test_post_new_event_redirects_to_detail(client):
    response = client.post("/events/new", data={
        "place": "U Karla",
        "event_date": "2099-12-31",
        "event_time": "19:00",
        "description": "",
    }, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/events/")


def test_post_new_event_shows_delete_link(client):
    response = client.post("/events/new", data={
        "place": "U Karla",
        "event_date": "2099-12-31",
        "event_time": "19:00",
        "description": "",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert "delete" in response.text.lower()


def test_post_new_event_missing_place(client):
    response = client.post("/events/new", data={
        "place": "",
        "event_date": "2099-12-31",
        "event_time": "19:00",
    })
    assert response.status_code == 200
    assert "Nový event" in response.text  # re-shown form
```

- [ ] **Step 2: Run tests to see them fail**

```bash
pytest tests/test_events.py -v
```

Expected: FAIL

- [ ] **Step 3: Add GET/POST /events/new routes to main.py**

```python
@app.get("/events/new", response_class=HTMLResponse)
async def new_event_form(request: Request):
    return templates.TemplateResponse("event_new.html", {"request": request, "errors": {}})


@app.post("/events/new")
async def create_event(
    request: Request,
    place: str = Form(""),
    event_date: str = Form(""),
    event_time: str = Form(""),
    description: str = Form(""),
):
    errors = {}
    if not place.strip():
        errors["place"] = "Zadaj miesto"
    if not event_date.strip():
        errors["event_date"] = "Zadaj dátum"
    if not event_time.strip():
        errors["event_time"] = "Zadaj čas"

    if errors:
        return templates.TemplateResponse("event_new.html", {
            "request": request,
            "errors": errors,
            "place": place,
            "event_date": event_date,
            "event_time": event_time,
            "description": description,
        })

    result = database.create_event(place.strip(), event_date.strip(), event_time.strip(), description.strip() or None)
    delete_url = f"/events/{result['id']}/delete?token={result['delete_token']}"
    request.session["flash"] = {
        "type": "warning",
        "message": f"⚠️ Ulož si tajný link na zmazanie eventu (zobrazí sa len raz):<br>"
                   f"<code>{request.url_for('delete_event_confirm', event_id=result['id'])}?token={result['delete_token']}</code>"
    }
    return RedirectResponse(url=f"/events/{result['id']}", status_code=303)
```

- [ ] **Step 4: Create templates/event_new.html**

```html
<!-- templates/event_new.html -->
{% extends "base.html" %}
{% block title %}Nový event — PivoProjekt{% endblock %}
{% block content %}

<a href="/" class="back-link">← Späť</a>
<h1 style="margin-bottom:24px">🍺 Nový event</h1>

<form method="post" action="/events/new">
  <div class="form-group">
    <label for="place">Miesto (pub / hostinec)</label>
    <input type="text" id="place" name="place" value="{{ place or '' }}" placeholder="napr. Hostinec U Karla" required>
    {% if errors.place %}<div class="form-error">{{ errors.place }}</div>{% endif %}
  </div>

  <div class="form-row">
    <div class="form-group">
      <label for="event_date">Dátum</label>
      <input type="date" id="event_date" name="event_date" value="{{ event_date or '' }}" required>
      {% if errors.event_date %}<div class="form-error">{{ errors.event_date }}</div>{% endif %}
    </div>
    <div class="form-group">
      <label for="event_time">Čas</label>
      <input type="time" id="event_time" name="event_time" value="{{ event_time or '' }}" required>
      {% if errors.event_time %}<div class="form-error">{{ errors.event_time }}</div>{% endif %}
    </div>
  </div>

  <div class="form-group">
    <label for="description">Popis (voliteľné)</label>
    <input type="text" id="description" name="description" value="{{ description or '' }}" placeholder="napr. Oslavujeme Janovu novú robotu 😄">
  </div>

  <button type="submit" class="btn btn-primary" style="width:100%;padding:12px;font-size:1rem">
    Vytvoriť event →
  </button>
</form>

{% endblock %}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_events.py -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add main.py templates/event_new.html tests/test_events.py
git commit -m "feat: create event form with validation and flash delete link"
```

---

## Task 7: Event Detail Page

**Files:**
- Modify: `main.py` — add GET `/events/{id}`
- Create: `templates/event_detail.html`
- Modify: `tests/test_events.py`

- [ ] **Step 1: Add tests to test_events.py**

Append to `tests/test_events.py`:

```python
def test_event_detail(client, sample_event):
    event_id = sample_event["id"]
    response = client.get(f"/events/{event_id}")
    assert response.status_code == 200
    assert "Hostinec U Karla" in response.text
    assert "Idem" in response.text
    assert "Neidem" in response.text


def test_event_detail_not_found(client):
    response = client.get("/events/nonexistent-id")
    assert response.status_code == 404
```

- [ ] **Step 2: Run new tests to see them fail**

```bash
pytest tests/test_events.py::test_event_detail tests/test_events.py::test_event_detail_not_found -v
```

Expected: FAIL

- [ ] **Step 3: Add GET /events/{id} route to main.py**

```python
from fastapi import HTTPException


@app.get("/events/{event_id}", response_class=HTMLResponse, name="event_detail")
async def event_detail(event_id: str, request: Request):
    event = database.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404)
    rsvps = database.get_rsvps(event_id)
    going = [r for r in rsvps if r["going"]]
    not_going = [r for r in rsvps if not r["going"]]
    flash = request.session.pop("flash", None)
    return templates.TemplateResponse("event_detail.html", {
        "request": request,
        "event": event,
        "going": going,
        "not_going": not_going,
        "flash": flash,
    })
```

Also add exception handlers at the bottom of `main.py`:

```python
from fastapi.responses import HTMLResponse as _HTMLResponse
from fastapi.exceptions import HTTPException as StarletteHTTPException


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return templates.TemplateResponse("404.html", {"request": request, "flash": None}, status_code=404)


@app.exception_handler(403)
async def forbidden_handler(request: Request, exc):
    return templates.TemplateResponse("403.html", {"request": request, "flash": None}, status_code=403)
```

- [ ] **Step 4: Create templates/event_detail.html**

```html
<!-- templates/event_detail.html -->
{% extends "base.html" %}
{% block title %}{{ event.place }} — PivoProjekt{% endblock %}
{% block content %}

<a href="/" class="back-link">← Späť na zoznam</a>

<div class="event-header">
  <div class="event-title">🍺 {{ event.place }}</div>
  <div class="event-meta">📅 {{ event.event_date }} o {{ event.event_time }}</div>
  {% if event.description %}
  <div class="event-desc">📝 {{ event.description }}</div>
  {% endif %}
</div>

<div class="rsvp-summary">
  <div class="rsvp-box rsvp-box-going">
    <div class="rsvp-count">{{ going | length }}</div>
    <div class="rsvp-label">idú ✅</div>
    <div class="rsvp-names">{{ going | map(attribute='name') | join(', ') }}</div>
  </div>
  <div class="rsvp-box rsvp-box-not">
    <div class="rsvp-count">{{ not_going | length }}</div>
    <div class="rsvp-label">nejdú ❌</div>
    <div class="rsvp-names">{{ not_going | map(attribute='name') | join(', ') }}</div>
  </div>
</div>

<div class="rsvp-form">
  <h3>Hlásiš sa?</h3>
  <form method="post" action="/events/{{ event.id }}/rsvp">
    <div class="form-group">
      <input type="text" name="name" placeholder="Tvoje meno" required>
      {% if rsvp_error %}<div class="form-error">{{ rsvp_error }}</div>{% endif %}
    </div>
    <div class="rsvp-buttons">
      <button type="submit" name="going" value="true" class="btn btn-success">✅ Idem!</button>
      <button type="submit" name="going" value="false" class="btn btn-danger">❌ Neidem</button>
    </div>
  </form>
</div>

<p class="organizer-hint">Si organizátor? Použi tajný link na zmazanie eventu.</p>

{% endblock %}
```

- [ ] **Step 5: Create templates/404.html and templates/403.html**

```html
<!-- templates/404.html -->
{% extends "base.html" %}
{% block title %}404 — PivoProjekt{% endblock %}
{% block content %}
<div class="error-page">
  <h1>404</h1>
  <p>Tento event neexistuje.</p>
  <a href="/" class="btn btn-primary">← Domov</a>
</div>
{% endblock %}
```

```html
<!-- templates/403.html -->
{% extends "base.html" %}
{% block title %}403 — PivoProjekt{% endblock %}
{% block content %}
<div class="error-page">
  <h1>403</h1>
  <p>Nesprávny alebo chýbajúci token.</p>
  <a href="/" class="btn btn-primary">← Domov</a>
</div>
{% endblock %}
```

- [ ] **Step 6: Run all tests**

```bash
pytest tests/ -v
```

Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add main.py templates/event_detail.html templates/404.html templates/403.html
git commit -m "feat: event detail page with RSVP summary and error pages"
```

---

## Task 8: RSVP Submission

**Files:**
- Modify: `main.py` — add POST `/events/{id}/rsvp`
- Create: `tests/test_rsvp.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_rsvp.py
def test_rsvp_going(client, sample_event):
    event_id = sample_event["id"]
    response = client.post(f"/events/{event_id}/rsvp",
        data={"name": "Marek", "going": "true"},
        follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == f"/events/{event_id}"


def test_rsvp_shows_name_on_detail(client, sample_event):
    event_id = sample_event["id"]
    client.post(f"/events/{event_id}/rsvp", data={"name": "Marek", "going": "true"})
    response = client.get(f"/events/{event_id}")
    assert "Marek" in response.text


def test_rsvp_overwrites(client, sample_event):
    event_id = sample_event["id"]
    client.post(f"/events/{event_id}/rsvp", data={"name": "Marek", "going": "true"})
    client.post(f"/events/{event_id}/rsvp", data={"name": "Marek", "going": "false"})
    import database
    rsvps = database.get_rsvps(event_id)
    assert len(rsvps) == 1
    assert rsvps[0]["going"] == 0


def test_rsvp_empty_name(client, sample_event):
    event_id = sample_event["id"]
    response = client.post(f"/events/{event_id}/rsvp",
        data={"name": "", "going": "true"},
        follow_redirects=True)
    assert response.status_code == 200
    assert "meno" in response.text.lower()


def test_rsvp_invalid_event(client):
    response = client.post("/events/nonexistent/rsvp",
        data={"name": "Marek", "going": "true"})
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to see them fail**

```bash
pytest tests/test_rsvp.py -v
```

Expected: FAIL

- [ ] **Step 3: Add POST /events/{id}/rsvp route to main.py**

```python
@app.post("/events/{event_id}/rsvp")
async def submit_rsvp(
    event_id: str,
    request: Request,
    name: str = Form(""),
    going: str = Form("true"),
):
    event = database.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404)

    if not name.strip():
        rsvps = database.get_rsvps(event_id)
        going_list = [r for r in rsvps if r["going"]]
        not_going_list = [r for r in rsvps if not r["going"]]
        return templates.TemplateResponse("event_detail.html", {
            "request": request,
            "event": event,
            "going": going_list,
            "not_going": not_going_list,
            "rsvp_error": "Zadaj svoje meno",
            "flash": None,
        })

    database.upsert_rsvp(event_id, name.strip(), going == "true")
    return RedirectResponse(url=f"/events/{event_id}", status_code=303)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_rsvp.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_rsvp.py
git commit -m "feat: RSVP submission with upsert and validation"
```

---

## Task 9: Delete Event Flow

**Files:**
- Modify: `main.py` — add GET/POST `/events/{id}/delete`
- Create: `templates/event_delete_confirm.html`
- Modify: `tests/test_events.py`

- [ ] **Step 1: Add tests to test_events.py**

Append:

```python
def test_get_delete_confirm_valid_token(client, sample_event):
    event_id = sample_event["id"]
    token = sample_event["delete_token"]
    response = client.get(f"/events/{event_id}/delete?token={token}")
    assert response.status_code == 200
    assert "zmazať" in response.text.lower()


def test_get_delete_wrong_token(client, sample_event):
    event_id = sample_event["id"]
    response = client.get(f"/events/{event_id}/delete?token=wrong")
    assert response.status_code == 403


def test_post_delete_valid_token(client, sample_event):
    event_id = sample_event["id"]
    token = sample_event["delete_token"]
    response = client.post(f"/events/{event_id}/delete?token={token}",
        follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_post_delete_removes_event(client, sample_event):
    event_id = sample_event["id"]
    token = sample_event["delete_token"]
    client.post(f"/events/{event_id}/delete?token={token}", follow_redirects=True)
    import database
    assert database.get_event(event_id) is None


def test_post_delete_wrong_token(client, sample_event):
    event_id = sample_event["id"]
    response = client.post(f"/events/{event_id}/delete?token=wrong")
    assert response.status_code == 403
```

- [ ] **Step 2: Run new tests to see them fail**

```bash
pytest tests/test_events.py -k "delete" -v
```

Expected: FAIL

- [ ] **Step 3: Add delete routes to main.py**

```python
@app.get("/events/{event_id}/delete", response_class=HTMLResponse, name="delete_event_confirm")
async def delete_event_confirm(event_id: str, request: Request, token: str = ""):
    event = database.get_event(event_id)
    if not event or event["delete_token"] != token:
        raise HTTPException(status_code=403)
    return templates.TemplateResponse("event_delete_confirm.html", {
        "request": request,
        "event": event,
        "token": token,
        "flash": None,
    })


@app.post("/events/{event_id}/delete")
async def delete_event(event_id: str, request: Request, token: str = ""):
    ok = database.delete_event(event_id, token)
    if not ok:
        raise HTTPException(status_code=403)
    request.session["flash"] = {"type": "success", "message": "Event bol zmazaný."}
    return RedirectResponse(url="/", status_code=303)
```

- [ ] **Step 4: Create templates/event_delete_confirm.html**

```html
<!-- templates/event_delete_confirm.html -->
{% extends "base.html" %}
{% block title %}Zmazať event — PivoProjekt{% endblock %}
{% block content %}

<div class="danger-box">
  <h2>Naozaj chceš zmazať tento event?</h2>
  <p>🍺 <strong>{{ event.place }}</strong> — {{ event.event_date }} o {{ event.event_time }}<br>
  Táto akcia je nevratná. Zmažú sa aj všetky RSVP odpovede.</p>
  <div class="danger-actions">
    <a href="/events/{{ event.id }}" class="btn btn-secondary">Zrušiť</a>
    <form method="post" action="/events/{{ event.id }}/delete?token={{ token }}">
      <button type="submit" class="btn btn-danger">Áno, zmazať</button>
    </form>
  </div>
</div>

{% endblock %}
```

- [ ] **Step 5: Run all tests**

```bash
pytest tests/ -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add main.py templates/event_delete_confirm.html tests/test_events.py
git commit -m "feat: delete event flow with token verification"
```

---

## Task 10: Final Wiring and Smoke Test

**Files:**
- No new files — verify end-to-end works manually

- [ ] **Step 1: Run full test suite**

```bash
pytest tests/ -v --tb=short
```

Expected: all PASS

- [ ] **Step 2: Start app and do a manual smoke test**

```bash
uvicorn main:app --reload
```

Open http://localhost:8000 and verify:
1. Home page loads with "Žiadne nadchádzajúce eventy"
2. Click "+ Nový event" → fill form → submit → see flash with delete link
3. RSVP as "Marek" going → name appears in green box
4. RSVP as "Jano" not going → name appears in red box
5. RSVP as "Marek" not going → Marek moves to red box (overwrite)
6. Visit delete link → confirm → redirected home with "Event bol zmazaný"
7. Wrong delete token → 403 page
8. Visit /events/nonexistent → 404 page

- [ ] **Step 3: Push to GitLab**

```bash
git push
```

- [ ] **Step 4: Final commit (if any fixes needed)**

```bash
git add -p
git commit -m "fix: smoke test fixes"
git push
```
