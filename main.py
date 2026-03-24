# main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

import database


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.create_tables()
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key="dev-secret-change-in-prod")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


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
        return templates.TemplateResponse(request, "event_new.html", {
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
                   f"<code>{delete_url}</code>"
    }
    return RedirectResponse(url=f"/events/{result['id']}", status_code=303)


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
