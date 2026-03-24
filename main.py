# main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI, Form, Request
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
