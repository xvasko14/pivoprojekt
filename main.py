# main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

import os
from datetime import date as date_type
import database


_DAYS = ["Pondelok", "Utorok", "Streda", "Štvrtok", "Piatok", "Sobota", "Nedeľa"]
_MONTHS = [
    "", "januára", "februára", "marca", "apríla", "mája", "júna",
    "júla", "augusta", "septembra", "októbra", "novembra", "decembra"
]


def format_date(value: str) -> str:
    """Convert ISO date string to Slovak human-readable format."""
    try:
        d = date_type.fromisoformat(value)
        return f"{_DAYS[d.weekday()]} {d.day}. {_MONTHS[d.month]}"
    except (ValueError, TypeError):
        return value


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.create_tables()
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SECRET_KEY", "dev-secret-change-in-prod"))
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
templates.env.filters["format_date"] = format_date


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    flash = request.session.pop("flash", None)
    upcoming, past = database.get_all_events()
    return templates.TemplateResponse(request, "home.html", {
        "upcoming": upcoming,
        "past": past,
        "flash": flash,
    })


@app.get("/events/new", response_class=HTMLResponse)
async def new_event_form(request: Request):
    return templates.TemplateResponse(request, "event_new.html", {"errors": {}})


@app.post("/events/new")
async def create_event(
    request: Request,
    title: str = Form(""),
    place: str = Form(""),
    event_date: str = Form(""),
    event_time: str = Form(""),
    description: str = Form(""),
    boys_only: str = Form(""),
):
    errors = {}
    if not place.strip():
        errors["place"] = "Zadaj miesto"
    if not event_date.strip():
        errors["event_date"] = "Zadaj dátum"
    if not event_time.strip():
        errors["event_time"] = "Zadaj čas"

    if errors:
        return templates.TemplateResponse(request, "event_new.html", {
            "errors": errors,
            "title": title,
            "place": place,
            "event_date": event_date,
            "event_time": event_time,
            "description": description,
            "boys_only": boys_only,
        })

    result = database.create_event(place.strip(), event_date.strip(), event_time.strip(), description.strip() or None, title.strip() or None, boys_only == "on")
    request.session["flash"] = {"type": "success", "message": "✅ Event vytvorený!"}
    return RedirectResponse(url=f"/events/{result['id']}", status_code=303)


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
        flash = request.session.pop("flash", None)
        return templates.TemplateResponse(request, "event_detail.html", {
            "event": event,
            "going": going_list,
            "not_going": not_going_list,
            "rsvp_error": "Zadaj svoje meno",
            "flash": flash,
        })

    database.upsert_rsvp(event_id, name.strip(), going == "true")
    return RedirectResponse(url=f"/events/{event_id}", status_code=303)


@app.post("/events/{event_id}/rsvp/{rsvp_id}/delete")
async def delete_rsvp(event_id: str, rsvp_id: int, request: Request):
    if not database.get_event(event_id):
        raise HTTPException(status_code=404)
    database.delete_rsvp(rsvp_id)
    return RedirectResponse(url=f"/events/{event_id}", status_code=303)


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
    title: str = Form(""),
    place: str = Form(""),
    event_date: str = Form(""),
    event_time: str = Form(""),
    description: str = Form(""),
    boys_only: str = Form(""),
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
            "event": {**event, "title": title, "place": place, "event_date": event_date,
                      "event_time": event_time, "description": description, "boys_only": boys_only == "on"},
            "errors": errors,
        })

    database.update_event(event_id, place.strip(), event_date.strip(),
                          event_time.strip(), description.strip() or None, title.strip() or None, boys_only == "on")
    return RedirectResponse(url=f"/events/{event_id}", status_code=303)


@app.get("/events/{event_id}", response_class=HTMLResponse, name="event_detail")
async def event_detail(event_id: str, request: Request):
    event = database.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404)
    rsvps = database.get_rsvps(event_id)
    going = [r for r in rsvps if r["going"]]
    not_going = [r for r in rsvps if not r["going"]]
    flash = request.session.pop("flash", None)
    return templates.TemplateResponse(request, "event_detail.html", {
        "event": event,
        "going": going,
        "not_going": not_going,
        "flash": flash,
    })


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse(request, "404.html", {}, status_code=404)


@app.exception_handler(403)
async def forbidden_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse(request, "403.html", {}, status_code=403)
