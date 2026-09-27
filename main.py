"""
main.py
Initializes the FastAPI app, static files, templates, database, and routes.

Run locally with:
    uvicorn app.main:app --reload
Then open http://127.0.0.1:8000
"""

import logging
import os
import secrets

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.routes import router

logger = logging.getLogger(__name__)
app = FastAPI(title="FitBuddy - AI Fitness Plan Generator")
session_secret = os.getenv("SESSION_SECRET")
if not session_secret:
    session_secret = secrets.token_urlsafe(32)
    if os.getenv("COOKIE_SECURE", "false").lower() == "true":
        logger.error(
            "SESSION_SECRET is not configured. Sessions will be invalid after a restart "
            "and will not work reliably across multiple instances."
        )
    else:
        logger.warning(
            "SESSION_SECRET is not configured; a temporary key is being used. "
            "Set a persistent secret in production."
        )
app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret,
    same_site="lax",
    https_only=os.getenv("COOKIE_SECURE", "false").lower() == "true",
)

app.mount("/static", StaticFiles(directory="static"), name="static")

init_db()

app.include_router(router)


@app.get("/healthz", include_in_schema=False)
def health_check():
    from sqlalchemy import text

    from app.database import engine

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok"}
