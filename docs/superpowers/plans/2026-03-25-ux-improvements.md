# UX Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add human-readable Slovak dates, open delete (no token), names on home cards, and edit event functionality.

**Architecture:** All changes are in-place modifications to existing files (`main.py`, `database.py`, templates). One new template (`event_edit.html`). No schema changes — `delete_token` column stays in DB unused.

**Tech Stack:** FastAPI, SQLite, Jinja2, pytest — same as existing app.

---

## File Map

| File | Change |
|------|--------|
| `main.py` | Add `format_date` Jinja2 filter; update delete routes (drop token check); add GET/POST `/events/{id}/edit` |
| `database.py` | Add `delete_event_by_id()`; add `update_event()`; update `get_all_events()` to return `going_names` |
| `templates/home.html` | Show names on upcoming cards; apply `format_date` |
| `templates/event_detail.html` | Apply `format_date`; add Edit + Delete buttons; remove organizer hint |
| `templates/event_delete_confirm.html` | Remove `?token=...` from form action; apply `format_date` |
| `templates/event_edit.html` | New — pre-filled edit form |
| `tests/test_events.py` | Update delete tests (no token), add edit tests |
| `tests/test_filters.py` | New — unit tests for `format_date` |

---

### Task 1: format_date Jinja2 filter

**Files:**
- Modify: `main.py`
- Create: `tests/test_filters.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_filters.py
import pytest
from main import format_date


def test_format_date_basic():
    assert format_date("2026-03-28") == "Sobota 28. marca"


def test_format_date_months():
    assert format_date("2026-01-01") == "Štvrtok 1. januára"
    assert format_date("2026-12-31") == "Štvrtok 31. decembra"


def test_format_date_invalid():
    assert format_date("not-a-date") == "not-a-date"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/vasko/osobne/Projekty/PivoProjekt
.venv/bin/pytest tests/test_filters.py -v
```
Expected: FAIL — `ImportError: cannot import name 'format_date'`

- [ ] **Step 3: Add filter to main.py**

Add after the `import os` / `import database` imports, before the `lifespan` function:

```python
def format_date(value: str) -> str:
    """Convert ISO date string to Slovak human-readable format."""
    from datetime import date as date_type
    DAYS = ["Pondelok", "Utorok", "Streda", "Štvrtok", "Piatok", "Sobota", "Nedeľa"]
    MONTHS = [
        "", "januára", "februára", "marca", "apríla", "mája", "júna",
        "júla", "augusta", "septembra", "októbra", "novembra", "decembra"
    ]
    try:
        d = date_type.fromisoformat(value)
        return f"{DAYS[d.weekday()]} {d.day}. {MONTHS[d.month]}"
    except (ValueError, TypeError):
        return value
```

Then register it as a Jinja2 filter after `templates = Jinja2Templates(directory="templates")`:

```python
templates.env.filters["format_date"] = format_date
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_filters.py -v
```
Expected: 3 PASS

- [ ] **Step 5: Apply filter in templates**

In `templates/home.html`, replace both date occurrences:

```html
<!-- upcoming cards (line ~13): -->
📅 {{ event.event_date | format_date }} o {{ event.event_time }}

<!-- history list (line ~28): -->
<span>{{ event.event_date | format_date }} · ✅ {{ event.going_count }} išlo</span>
```

In `templates/event_detail.html`, replace line 10:
```html
<div class="event-meta">📅 {{ event.event_date | format_date }} o {{ event.event_time }}</div>
```

In `templates/event_delete_confirm.html`, replace line 8:
```html
🍺 <strong>{{ event.place }}</strong> — {{ event.event_date | format_date }} o {{ event.event_time }}<br>
```

- [ ] **Step 6: Run all tests**

```bash
.venv/bin/pytest -v
```
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add main.py templates/home.html templates/event_detail.html templates/event_delete_confirm.html tests/test_filters.py
git commit -m "feat: add format_date Jinja2 filter with Slovak day/month names"
```

---

### Task 2: Delete without token

**Files:**
- Modify: `database.py`
- Modify: `main.py`
- Modify: `templates/event_delete_confirm.html`
- Modify: `tests/test_events.py`

- [ ] **Step 1: Update tests first**

Replace the delete-related tests in `tests/test_events.py`. The old tests check token validation — the new behaviour is: anyone can delete, no token needed.

Replace these 5 tests:

```python
def test_get_delete_confirm(client, sample_event):
    """Anyone can access the delete confirmation page."""
    event_id = sample_event["id"]
    response = client.get(f"/events/{event_id}/delete")
    assert response.status_code == 200
    assert "zmazať" in response.text.lower()


def test_get_delete_confirm_nonexistent(client):
    response = client.get("/events/nonexistent-id/delete")
    assert response.status_code == 404


def test_post_delete_redirects_home(client, sample_event):
    event_id = sample_event["id"]
    response = client.post(f"/events/{event_id}/delete", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_post_delete_removes_event(client, sample_event):
    event_id = sample_event["id"]
    client.post(f"/events/{event_id}/delete", follow_redirects=True)
    assert database.get_event(event_id) is None


def test_post_delete_nonexistent(client):
    response = client.post("/events/nonexistent-id/delete")
    assert response.status_code == 404
```

Remove these old tests (they test token logic that no longer exists):
- `test_get_delete_confirm_valid_token`
- `test_get_delete_wrong_token`
- `test_post_delete_valid_token`
- `test_post_delete_wrong_token`

Also update `test_post_new_event_shows_delete_link` — flash no longer contains "delete". The detail page will have a delete link, but this test doesn't follow redirects to the detail page fully. Change it to just verify the redirect:

```python
def test_post_new_event_creates_event(client):
    response = client.post("/events/new", data={
        "place": "U Karla",
        "event_date": "2099-12-31",
        "event_time": "19:00",
        "description": "",
    }, follow_redirects=True)
    assert response.status_code == 200
    assert "U Karla" in response.text
```

- [ ] **Step 2: Run updated tests — some should fail**

```bash
.venv/bin/pytest tests/test_events.py -v
```
Expected: new delete tests FAIL (routes still check token)

- [ ] **Step 3: Add delete_event_by_id to database.py**

Add after `delete_event`:

```python
def delete_event_by_id(event_id: str) -> bool:
    """Delete event by ID only, no token check. Returns True if deleted."""
    with get_connection() as conn:
        result = conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
    return result.rowcount == 1
```

- [ ] **Step 4: Update delete routes in main.py**

Replace the two delete route handlers:

```python
@app.get("/events/{event_id}/delete", response_class=HTMLResponse, name="delete_event_confirm")
async def delete_event_confirm(event_id: str, request: Request):
    event = database.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(request, "event_delete_confirm.html", {
        "event": event,
        "flash": None,
    })


@app.post("/events/{event_id}/delete")
async def delete_event(event_id: str, request: Request):
    ok = database.delete_event_by_id(event_id)
    if not ok:
        raise HTTPException(status_code=404)
    request.session["flash"] = {"type": "success", "message": "Event bol zmazaný."}
    return RedirectResponse(url="/", status_code=303)
```

- [ ] **Step 5: Update event_delete_confirm.html**

Replace the form action line (remove `?token=...`):

```html
<form method="post" action="/events/{{ event.id }}/delete">
```

- [ ] **Step 6: Update flash message in create_event route in main.py**

Replace the flash assignment in the `create_event` POST handler:

```python
request.session["flash"] = {"type": "success", "message": "✅ Event vytvorený!"}
```

- [ ] **Step 7: Run tests**

```bash
.venv/bin/pytest -v
```
Expected: all pass

- [ ] **Step 8: Commit**

```bash
git add main.py database.py templates/event_delete_confirm.html tests/test_events.py
git commit -m "feat: open delete — anyone can delete event without token"
```

---

### Task 3: Names on home cards

**Files:**
- Modify: `database.py`
- Modify: `templates/home.html`
- Modify: `tests/test_db.py`

- [ ] **Step 1: Add test for going_names in get_all_events**

Add to `tests/test_db.py`:

```python
def test_get_all_events_going_names():
    database.create_event("Pub A", "2099-01-01", "18:00", None)
    events_raw = database.create_event("Pub B", "2099-02-01", "19:00", None)
    event_id = events_raw["id"]
    database.upsert_rsvp(event_id, "Jano", True)
    database.upsert_rsvp(event_id, "Ferko", True)
    database.upsert_rsvp(event_id, "Miro", False)
    upcoming, _ = database.get_all_events()
    pub_b = next(e for e in upcoming if e["place"] == "Pub B")
    assert pub_b["going_names"] == ["Jano", "Ferko"]


def test_get_all_events_going_names_empty():
    database.create_event("Pub C", "2099-03-01", "20:00", None)
    upcoming, _ = database.get_all_events()
    pub_c = next(e for e in upcoming if e["place"] == "Pub C")
    assert pub_c["going_names"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_db.py -v
```
Expected: FAIL — `KeyError: 'going_names'`

- [ ] **Step 3: Update get_all_events in database.py**

Replace the current `get_all_events` function:

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
```

- [ ] **Step 4: Run DB tests**

```bash
.venv/bin/pytest tests/test_db.py -v
```
Expected: all pass

- [ ] **Step 5: Update home.html to show names on upcoming cards**

Replace the card content block (the `<a href=... class="card">` block) in `templates/home.html`:

```html
{% for event in upcoming %}
<a href="/events/{{ event.id }}" class="card">
  <div class="card-place">🍺 {{ event.place }}</div>
  <div class="card-datetime">
    📅 {{ event.event_date | format_date }} o {{ event.event_time }}
  </div>
  {% if event.going_names %}
  <div class="card-going">
    ✅
    {% if event.going_names | length <= 3 %}
      {{ event.going_names | join(', ') }}
    {% else %}
      {{ event.going_names[:3] | join(', ') }} a {{ event.going_names | length - 3 }} ďalší
    {% endif %}
  </div>
  {% else %}
  <div class="card-going" style="color:#aaa">Nikto zatiaľ</div>
  {% endif %}
</a>
{% endfor %}
```

- [ ] **Step 6: Run all tests**

```bash
.venv/bin/pytest -v
```
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add database.py templates/home.html tests/test_db.py
git commit -m "feat: show going names on home cards"
```

---

### Task 4: Edit event

**Files:**
- Modify: `database.py`
- Modify: `main.py`
- Create: `templates/event_edit.html`
- Modify: `templates/event_detail.html`
- Modify: `tests/test_events.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_events.py`:

```python
def test_get_edit_form_shows_prefilled(client, sample_event):
    event_id = sample_event["id"]
    response = client.get(f"/events/{event_id}/edit")
    assert response.status_code == 200
    assert "Hostinec U Karla" in response.text
    assert "Upraviť" in response.text


def test_get_edit_form_not_found(client):
    response = client.get("/events/nonexistent-id/edit")
    assert response.status_code == 404


def test_post_edit_updates_event(client, sample_event):
    event_id = sample_event["id"]
    response = client.post(f"/events/{event_id}/edit", data={
        "place": "Nový Pub",
        "event_date": "2099-06-15",
        "event_time": "20:00",
        "description": "Zmenené",
    }, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == f"/events/{event_id}"
    updated = database.get_event(event_id)
    assert updated["place"] == "Nový Pub"
    assert updated["event_date"] == "2099-06-15"


def test_post_edit_missing_place(client, sample_event):
    event_id = sample_event["id"]
    response = client.post(f"/events/{event_id}/edit", data={
        "place": "",
        "event_date": "2099-06-15",
        "event_time": "20:00",
    })
    assert response.status_code == 200
    assert "Upraviť" in response.text


def test_post_edit_not_found(client):
    response = client.post("/events/nonexistent-id/edit", data={
        "place": "Pub",
        "event_date": "2099-06-15",
        "event_time": "20:00",
    })
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_events.py -k "edit" -v
```
Expected: FAIL — 404 (routes don't exist yet)

- [ ] **Step 3: Add update_event to database.py**

Add after `upsert_rsvp`:

```python
def update_event(event_id: str, place: str, event_date: str, event_time: str, description: str | None) -> bool:
    """Update event fields. Returns True if found and updated."""
    with get_connection() as conn:
        result = conn.execute(
            "UPDATE events SET place=?, event_date=?, event_time=?, description=? WHERE id=?",
            (place, event_date, event_time, description, event_id),
        )
    return result.rowcount == 1
```

- [ ] **Step 4: Add edit routes to main.py**

Add before the `event_detail` route (so the more specific `/events/{id}/edit` path is matched before `/events/{id}`):

```python
@app.get("/events/{event_id}/edit", response_class=HTMLResponse)
async def edit_event_form(event_id: str, request: Request):
    event = database.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(request, "event_edit.html", {
        "event": event,
        "errors": {},
    })


@app.post("/events/{event_id}/edit")
async def edit_event(
    event_id: str,
    request: Request,
    place: str = Form(""),
    event_date: str = Form(""),
    event_time: str = Form(""),
    description: str = Form(""),
):
    event = database.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404)

    errors = {}
    if not place.strip():
        errors["place"] = "Zadaj miesto"
    if not event_date.strip():
        errors["event_date"] = "Zadaj dátum"
    if not event_time.strip():
        errors["event_time"] = "Zadaj čas"

    if errors:
        return templates.TemplateResponse(request, "event_edit.html", {
            "event": {**event, "place": place, "event_date": event_date,
                      "event_time": event_time, "description": description},
            "errors": errors,
        })

    database.update_event(event_id, place.strip(), event_date.strip(),
                          event_time.strip(), description.strip() or None)
    return RedirectResponse(url=f"/events/{event_id}", status_code=303)
```

- [ ] **Step 5: Create templates/event_edit.html**

```html
<!-- templates/event_edit.html -->
{% extends "base.html" %}
{% block title %}Upraviť event — PivoProjekt{% endblock %}
{% block content %}

<a href="/events/{{ event.id }}" class="back-link">← Späť</a>
<h1 style="margin-bottom:24px">✏️ Upraviť event</h1>

<form method="post" action="/events/{{ event.id }}/edit">
  <div class="form-group">
    <label for="place">Miesto (pub / hostinec)</label>
    <input type="text" id="place" name="place" value="{{ event.place }}" placeholder="napr. Hostinec U Karla" required>
    {% if errors.place %}<div class="form-error">{{ errors.place }}</div>{% endif %}
  </div>

  <div class="form-row">
    <div class="form-group">
      <label for="event_date">Dátum</label>
      <input type="date" id="event_date" name="event_date" value="{{ event.event_date }}" required>
      {% if errors.event_date %}<div class="form-error">{{ errors.event_date }}</div>{% endif %}
    </div>
    <div class="form-group">
      <label for="event_time">Čas</label>
      <input type="time" id="event_time" name="event_time" value="{{ event.event_time }}" required>
      {% if errors.event_time %}<div class="form-error">{{ errors.event_time }}</div>{% endif %}
    </div>
  </div>

  <div class="form-group">
    <label for="description">Popis (voliteľné)</label>
    <input type="text" id="description" name="description" value="{{ event.description or '' }}" placeholder="napr. Oslavujeme Janovu novú robotu 😄">
  </div>

  <button type="submit" class="btn btn-primary" style="width:100%;padding:12px;font-size:1rem">
    Uložiť zmeny →
  </button>
</form>

{% endblock %}
```

- [ ] **Step 6: Update event_detail.html**

Replace the organizer hint line and add edit + delete buttons. Replace line 43 (`<p class="organizer-hint">...`):

```html
<div class="event-actions">
  <a href="/events/{{ event.id }}/edit" class="btn btn-secondary">✏️ Upraviť event</a>
  <a href="/events/{{ event.id }}/delete" class="btn btn-danger">🗑️ Zmazať event</a>
</div>
```

- [ ] **Step 7: Run all tests**

```bash
.venv/bin/pytest -v
```
Expected: all pass

- [ ] **Step 8: Commit**

```bash
git add database.py main.py templates/event_edit.html templates/event_detail.html tests/test_events.py
git commit -m "feat: edit event — anyone can edit place, date, time, description"
```

---

### Task 5: Push and deploy

- [ ] **Step 1: Run full test suite**

```bash
.venv/bin/pytest -v
```
Expected: all pass, 0 failures

- [ ] **Step 2: Push to GitLab**

```bash
git push
```

- [ ] **Step 3: Deploy to Fly.io**

```bash
fly deploy
```

Expected: `v2 deployed successfully`

- [ ] **Step 4: Smoke test on production**

Open [https://pivoproject.fly.dev](https://pivoproject.fly.dev) and verify:
- Dates show as "Piatok 28. marca" format
- Home cards show names of who's going
- Edit button works on event detail
- Delete button works without needing a token
