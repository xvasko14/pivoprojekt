# PivoProjekt — UX Improvements Design Spec

**Date:** 2026-03-25

## Overview

Four focused UX improvements to the existing PivoProjekt app. All changes are in-place modifications to existing files plus one new template and one new route pair.

## Changes

### 1. Human-readable dates

**Problem:** Dates display as `2026-03-28` — technical and unfriendly.

**Solution:** Add a `format_date` Jinja2 filter in `main.py`. Converts ISO date string to Slovak format: `Piatok 28. marca`. Slovak day and month names are hardcoded (no external library needed).

**Format:** `{day_name} {day}. {month_name}` — e.g., `Piatok 28. marca`

**Applies to:** All templates that display `event_date` — `home.html`, `event_detail.html`, `event_delete_confirm.html`, `event_edit.html`.

---

### 2. Delete without token

**Problem:** Delete requires a secret token link — overly complex for a trusted friend group.

**Solution:** Remove token verification from `GET /events/{id}/delete` and `POST /events/{id}/delete`. Anyone who navigates to the delete URL can delete the event after confirmation.

**Changes:**
- `main.py`: Remove token check from both delete routes. The `token` query parameter is ignored.
- `database.py`: Add `delete_event_by_id(event_id)` — deletes by ID only, no token check. The `delete_token` column stays in DB (no migration needed).
- `event_delete_confirm.html`: Remove token from form hidden input.
- `create_event` route: Flash message after creation changes from "save your delete link" warning to a simple "✅ Event vytvorený!" success message.

---

### 3. Names on home cards

**Problem:** Home cards show only `going_count` — you can't see who's coming without clicking in.

**Solution:** `get_all_events()` returns `going_names` alongside `going_count` — a list of names of people who RSVP'd as going. Home card displays up to 3 names inline, then `a N ďalší` for overflow.

**Display format:**
- 0 going: nothing (or `Nikto zatiaľ`)
- 1–3 going: `✅ Jano, Ferko, Miro`
- 4+ going: `✅ Jano, Ferko, Miro a 2 ďalší`

**Query change:** `get_all_events()` adds `GROUP_CONCAT` or fetches names via a second query per event. Simple approach: fetch all RSVPs for going people in one query, group in Python.

---

### 4. Edit event

**Problem:** Once created, an event can't be modified — wrong date or typo requires delete + recreate.

**Solution:** New `GET/POST /events/{id}/edit` routes. Anyone can edit any event (consistent with open delete policy).

**Fields editable:** place, event_date, event_time, description (all fields).

**Routes:**
| Method | Route | Description |
|--------|-------|-------------|
| GET | `/events/{id}/edit` | Pre-filled edit form |
| POST | `/events/{id}/edit` | Validate + update → redirect to detail |

**New files:**
- `templates/event_edit.html` — same form as `event_new.html`, pre-filled with current values

**New database function:**
- `update_event(event_id, place, event_date, event_time, description)` — updates all 4 fields

**UI:** "✏️ Upraviť event" button/link on event detail page (`event_detail.html`).

**Validation:** Same as create — place, date, time required. On error, re-render form with errors and current values.

---

## Files Changed

| File | Change |
|------|--------|
| `main.py` | Add `format_date` filter; update delete routes (remove token); add edit routes |
| `database.py` | Add `delete_event_by_id()`; add `update_event()`; update `get_all_events()` to include `going_names` |
| `templates/home.html` | Show names on cards |
| `templates/event_detail.html` | Add edit button |
| `templates/event_delete_confirm.html` | Remove token hidden input |
| `templates/event_new.html` | No change |
| `templates/event_edit.html` | New file — pre-filled edit form |

## Non-Goals

- Audit trail / who edited what
- Per-event permissions
- Undo functionality
