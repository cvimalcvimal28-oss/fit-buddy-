"""
main.py
Initializes the FastAPI app, static files, templates, database, and routes.

Run locally with:
    uvicorn app.main:app --reload
Then open http://127.0.0.1:8000
"""

import os
import secrets

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.routes import router

app = FastAPI(title="FitBuddy - AI Fitness Plan Generator")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET") or secrets.token_urlsafe(32),
    same_site="lax",
    https_only=os.getenv("COOKIE_SECURE", "false").lower() == "true",
)

app.mount("/static", StaticFiles(directory="static"), name="static")

init_db()

app.include_router(router)
