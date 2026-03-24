# PivoProjekt — Design Spec

**Date:** 2026-03-24

## Overview

A simple web app for organizing beer outings with friends. Replaces ad-hoc Facebook coordination. Anyone can create events, anyone can RSVP with their name — no login required.

## Goals

- Create beer outing events (pub, date, time, optional description)
- Friends RSVP by typing their name and clicking "Idem" / "Neidem"
- Public event list visible to anyone
- Full event history (past events stay visible)
- Organizer gets a one-time secret link to delete their event

## Non-Goals (v1)

- User accounts / authentication
- Event editing (only delete via secret link)
- Notifications or reminders
- Comments or chat
- Spam protection beyond obscurity

## Tech Stack

| Layer     | Technology                        |
|-----------|-----------------------------------|
| Backend   | Python · FastAPI                  |
| Database  | SQLite (`pivo.db`)                |
| Templates | Jinja2 (server-side rendered HTML)|
| Styling   | Plain CSS, no framework           |
| JS        | Minimal / none                    |

## Data Model

### `events`

| Column       | Type     | Notes                              |
|--------------|----------|------------------------------------|
| id           | TEXT     | UUID, primary key                  |
| place        | TEXT     | Pub / venue name                   |
| event_date   | TEXT     | ISO date string (YYYY-MM-DD)       |
| event_time   | TEXT     | HH:MM                              |
| description  | TEXT     | Optional note, nullable            |
| delete_token | TEXT     | UUID, never exposed in normal flow |
| created_at   | DATETIME | Auto-set on insert                 |

### `rsvps`

| Column     | Type     | Notes                        |
|------------|----------|------------------------------|
| id         | INTEGER  | Auto-increment primary key   |
| event_id   | TEXT     | FK → events.id               |
| name       | TEXT     | Person's name                |
| going      | BOOLEAN  | True = going, False = not    |
| created_at | DATETIME | Auto-set on insert           |

## Pages & Routes

| Method | Route                              | Description                                      |
|--------|------------------------------------|--------------------------------------------------|
| GET    | `/`                                | Home — upcoming events as cards, history below   |
| GET    | `/events/new`                      | Create event form                                |
| POST   | `/events/new`                      | Submit new event → redirect to detail page       |
| GET    | `/events/{id}`                     | Event detail — info, RSVP counts/names, form     |
| POST   | `/events/{id}/rsvp`                | Submit RSVP → redirect back to detail            |
| GET    | `/events/{id}/delete?token={token}`| Show delete confirmation page                    |
| POST   | `/events/{id}/delete?token={token}`| Delete event + all its RSVPs → redirect to home  |

## Page Designs

### `/` — Home

- Nav bar: "🍺 PivoProjekt" left, "+ Nový event" button right
- **Upcoming section:** events with `event_date >= today`, shown as cards in a row (2-3 per row on desktop). Each card shows: pub name, date+time, ✅ count of going.
- **History section:** events with `event_date < today`, shown as a compact list. Muted styling.

### `/events/{id}` — Detail

- Back link to home
- Event title (pub name), date+time, optional description
- Two summary boxes: green (going count + names), red (not going count + names)
- RSVP form: name input + "✅ Idem!" and "❌ Neidem" buttons (two separate submit buttons)
- Small footer note: "Si organizátor? Použi tajný link na zmazanie eventu."

### `/events/new` — Create Event

- Form fields: place (required), date (required), time (required), description (optional)
- Submit button: "Vytvoriť event →"
- After successful creation: redirect to event detail page, with a **one-time flash message** showing the delete link (`/events/{id}/delete?token={token}`)
- Flash message has a warning style and instructs the user to copy and save the link

### Delete flow

- GET `/events/{id}/delete?token={token}` → shows confirmation page ("Naozaj chceš zmazať tento event?")
- POST → deletes event + all RSVPs, redirects to home with a flash "Event bol zmazaný."
- If token is wrong or missing → 403 error page

## Error Handling

- Invalid event ID → 404 page
- Wrong delete token → 403 page
- Empty name on RSVP → form re-displayed with validation message
- Empty required fields on create → form re-displayed with validation message

## Deployment

- Local development: `uvicorn main:app --reload`
- Production target: Fly.io or Railway (free tier), SQLite file persisted via volume
- No environment-specific config needed for v1 (SQLite path hardcoded to `pivo.db`)

## Future Considerations (out of scope for v1)

- Simple group password for event creation
- RSVP remembered via cookie (name pre-filled)
- Multiple friend groups / namespaces
- Push/email reminders
