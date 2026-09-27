"""FastAPI endpoints for member authentication, workout plans, and feedback."""

import json
import hashlib
import logging
import os
import re
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import hash_password, verify_password
from app.database import get_db
from app.diet_chat import generate_diet_reply
from app.gemini_flash_generator import generate_nutrition_tip
from app.gemini_generator import generate_workout_plan
from app.models import DietChatMessage, User, UserFeedback, WorkoutPlan
from app.models import PasswordResetToken
from app.password_reset import send_password_reset_email
from app.updated_plan import generate_updated_plan

router = APIRouter()
templates = Jinja2Templates(directory="templates")
logger = logging.getLogger(__name__)

GOALS = {"Weight Loss", "Muscle Gain", "General Wellness"}
INTENSITIES = {"Low", "Medium", "High"}
FEEDBACK_CATEGORIES = {"Workout plan", "Website experience", "Gemini AI", "Other"}
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
FEEDBACK_VIEWER_EMAIL = "cvimalcvimal0@gmail.com"
PASSWORD_RESET_LIFETIME = timedelta(minutes=30)
PASSWORD_RESET_RESEND_WAIT = timedelta(minutes=1)


def get_signed_in_user(request: Request, db: Session) -> User | None:
    user_id = request.session.get("user_id")
    if not isinstance(user_id, int):
        return None
    return db.query(User).filter(User.id == user_id).first()


def sign_in_redirect() -> RedirectResponse:
    return RedirectResponse(url="/login?error=required", status_code=303)


def _get_valid_password_reset(db: Session, raw_token: str) -> PasswordResetToken | None:
    if not raw_token or len(raw_token) > 200:
        return None
    token_digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    return (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token_digest == token_digest,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > datetime.utcnow(),
        )
        .first()
    )


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    if get_signed_in_user(request, db):
        return RedirectResponse(url="/", status_code=303)

    errors = {
        "invalid": "That email and password don't match.",
        "required": "Please sign in to continue.",
    }
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "error": errors.get(request.query_params.get("error", "")),
            "notice": "Your password has been reset. Sign in with your new password."
            if request.query_params.get("reset") == "1"
            else None,
        },
    )


@router.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="forgot_password.html",
        context={"submitted": request.query_params.get("submitted") == "1"},
    )


@router.post("/forgot-password")
def request_password_reset(
    request: Request,
    email: str = Form(..., min_length=3, max_length=254),
    db: Session = Depends(get_db),
):
    normalized_email = email.strip().casefold()
    user = db.query(User).filter(User.email == normalized_email).first()
    now = datetime.utcnow()
    if user and user.password_hash:
        latest = (
            db.query(PasswordResetToken)
            .filter(PasswordResetToken.user_id == user.id)
            .order_by(PasswordResetToken.created_at.desc())
            .first()
        )
        if not latest or now - latest.created_at >= PASSWORD_RESET_RESEND_WAIT:
            db.query(PasswordResetToken).filter(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
            ).update({"used_at": now}, synchronize_session=False)
            raw_token = secrets.token_urlsafe(32)
            token_record = PasswordResetToken(
                user_id=user.id,
                token_digest=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
                expires_at=now + PASSWORD_RESET_LIFETIME,
            )
            db.add(token_record)
            db.commit()
            base_url = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
            parsed_base_url = urlparse(base_url)
            if parsed_base_url.scheme == "https" and parsed_base_url.netloc:
                send_password_reset_email(
                    user.email,
                    f"{base_url}/reset-password#token={raw_token}",
                )
            else:
                logger.error("Password reset email not sent: PUBLIC_BASE_URL must be an HTTPS URL.")
        else:
            db.rollback()

    return RedirectResponse(url="/forgot-password?submitted=1", status_code=303)


@router.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="reset_password.html",
        context={
            "token": "",
            "valid": False,
            "awaiting_token": True,
            "updated": request.query_params.get("updated") == "1",
        },
    )


@router.post("/reset-password", response_class=HTMLResponse)
def reset_password(
    request: Request,
    token: str = Form(..., min_length=20, max_length=200),
    password: str = Form(..., min_length=10, max_length=128),
    password_confirm: str = Form(..., max_length=128),
    db: Session = Depends(get_db),
):
    reset_record = _get_valid_password_reset(db, token)
    valid = reset_record is not None
    error = None
    if valid and password != password_confirm:
        error = "Those passwords don't match."
    elif valid and not password.strip():
        error = "Choose a password that is not blank."

    if not valid or error:
        return templates.TemplateResponse(
            request=request,
            name="reset_password.html",
            context={
                "token": token,
                "valid": valid,
                "awaiting_token": False,
                "updated": False,
                "error": error or "This reset link is invalid or expired. Request a new one.",
            },
            status_code=400,
        )

    claimed = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.id == reset_record.id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > datetime.utcnow(),
        )
        .update({"used_at": datetime.utcnow()}, synchronize_session=False)
    )
    if claimed != 1:
        db.rollback()
        return RedirectResponse(url="/forgot-password?submitted=1", status_code=303)

    user = db.query(User).filter(User.id == reset_record.user_id).first()
    if not user:
        db.rollback()
        return RedirectResponse(url="/forgot-password?submitted=1", status_code=303)
    now = datetime.utcnow()
    user.password_hash = hash_password(password)
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None),
    ).update({"used_at": now}, synchronize_session=False)
    db.commit()
    return RedirectResponse(url="/login?reset=1", status_code=303)


@router.post("/login")
def login(
    request: Request,
    email: str = Form(..., min_length=3, max_length=254),
    password: str = Form(..., max_length=128),
    db: Session = Depends(get_db),
):
    normalized_email = email.strip().casefold()
    user = db.query(User).filter(User.email == normalized_email).first()
    if not user or not verify_password(password, user.password_hash):
        return RedirectResponse(url="/login?error=invalid", status_code=303)

    request.session.clear()
    request.session["user_id"] = user.id
    return RedirectResponse(url="/", status_code=303)


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, db: Session = Depends(get_db)):
    if get_signed_in_user(request, db):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={"error": None},
    )


@router.post("/register", response_class=HTMLResponse)
def register(
    request: Request,
    name: str = Form(..., min_length=1, max_length=80),
    email: str = Form(..., min_length=3, max_length=254),
    age: int = Form(..., ge=10, le=90),
    weight: int = Form(..., ge=25, le=250),
    fitness_goal: str = Form(...),
    workout_intensity: str = Form(...),
    password: str = Form(..., min_length=10, max_length=128),
    password_confirm: str = Form(..., max_length=128),
    db: Session = Depends(get_db),
):
    normalized_email = email.strip().casefold()
    display_name = name.strip()
    if not display_name:
        error = "Please enter your name."
    elif not EMAIL_PATTERN.fullmatch(normalized_email):
        error = "Enter a valid email address."
    elif password != password_confirm:
        error = "Those passwords don't match."
    elif fitness_goal not in GOALS or workout_intensity not in INTENSITIES:
        error = "Choose a valid fitness goal and training intensity."
    elif db.query(User).filter(User.email == normalized_email).first():
        error = "That email is already registered. Please sign in or use another."
    else:
        user = User(
            user_id=f"FB{secrets.token_hex(8).upper()}",
            email=normalized_email,
            name=display_name,
            age=age,
            weight=weight,
            fitness_goal=fitness_goal,
            workout_intensity=workout_intensity,
            password_hash=hash_password(password),
        )
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            error = "That email is already registered. Please sign in or use another."
        else:
            db.refresh(user)
            request.session.clear()
            request.session["user_id"] = user.id
            return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={"error": error},
        status_code=400,
    )


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


@router.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    user = get_signed_in_user(request, db)
    if not user:
        return sign_in_redirect()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"user": user},
    )


@router.post("/generate-workout", response_class=HTMLResponse)
def generate_workout(
    request: Request,
    name: str = Form(..., min_length=1, max_length=80),
    age: int = Form(..., ge=10, le=90),
    weight: int = Form(..., ge=25, le=250),
    fitness_goal: str = Form(...),
    workout_intensity: str = Form(...),
    db: Session = Depends(get_db),
):
    user = get_signed_in_user(request, db)
    if not user:
        return sign_in_redirect()
    if fitness_goal not in GOALS or workout_intensity not in INTENSITIES:
        return RedirectResponse(url="/", status_code=303)

    user.name = name.strip() or user.name
    user.age, user.weight = age, weight
    user.fitness_goal, user.workout_intensity = fitness_goal, workout_intensity
    db.commit()

    plan = generate_workout_plan(user.name, age, weight, fitness_goal, workout_intensity)
    tip = generate_nutrition_tip(fitness_goal, workout_intensity)

    workout_plan = WorkoutPlan(
        user_id=user.id,
        original_plan=json.dumps(plan),
        nutrition_tip=tip,
    )
    db.add(workout_plan)
    db.commit()
    db.refresh(workout_plan)

    return templates.TemplateResponse(
        request=request,
        name="result.html",
        context={
            "user": user,
            "plan_id": workout_plan.id,
            "plan": plan,
            "nutrition_tip": tip,
            "updated_plan": None,
            "feedback": None,
        },
    )


@router.post("/submit-feedback", response_class=HTMLResponse)
def submit_feedback(
    request: Request,
    plan_id: int = Form(...),
    feedback: str = Form(..., min_length=1, max_length=2000),
    db: Session = Depends(get_db),
):
    user = get_signed_in_user(request, db)
    if not user:
        return sign_in_redirect()

    workout_plan = db.query(WorkoutPlan).filter(WorkoutPlan.id == plan_id).first()
    if not workout_plan or workout_plan.user_id != user.id:
        return RedirectResponse(url="/", status_code=303)

    updated = generate_updated_plan(workout_plan.original_plan, feedback)

    workout_plan.feedback = feedback
    workout_plan.updated_plan = json.dumps(updated)
    db.commit()
    db.refresh(workout_plan)

    return templates.TemplateResponse(
        request=request,
        name="result.html",
        context={
            "user": user,
            "plan_id": workout_plan.id,
            "plan": json.loads(workout_plan.original_plan),
            "nutrition_tip": workout_plan.nutrition_tip,
            "updated_plan": updated,
            "feedback": feedback,
        },
    )


@router.get("/feedback", response_class=HTMLResponse)
def feedback_page(request: Request, db: Session = Depends(get_db)):
    user = get_signed_in_user(request, db)
    if not user:
        return sign_in_redirect()
    return templates.TemplateResponse(
        request=request,
        name="feedback.html",
        context={
            "user": user,
            "submitted": request.query_params.get("submitted") == "1",
        },
    )


@router.post("/feedback")
def submit_user_feedback(
    request: Request,
    rating: int = Form(..., ge=1, le=5),
    category: str = Form(...),
    message: str = Form(..., min_length=1, max_length=2000),
    db: Session = Depends(get_db),
):
    user = get_signed_in_user(request, db)
    if not user:
        return sign_in_redirect()
    if category not in FEEDBACK_CATEGORIES or not message.strip():
        return RedirectResponse(url="/feedback?error=invalid", status_code=303)

    db.add(
        UserFeedback(
            user_id=user.id,
            rating=rating,
            category=category,
            message=message.strip(),
        )
    )
    db.commit()
    return RedirectResponse(url="/feedback?submitted=1", status_code=303)


@router.get("/feedback-inbox", response_class=HTMLResponse)
def feedback_inbox(request: Request, db: Session = Depends(get_db)):
    user = get_signed_in_user(request, db)
    if not user:
        return sign_in_redirect()
    if not user.email or user.email.casefold() != FEEDBACK_VIEWER_EMAIL:
        return HTMLResponse("Feedback inbox access is not enabled for this account.", status_code=403)

    feedback_entries = (
        db.query(UserFeedback)
        .join(User)
        .order_by(UserFeedback.created_at.desc())
        .limit(100)
        .all()
    )
    return templates.TemplateResponse(
        request=request,
        name="feedback_inbox.html",
        context={"user": user, "feedback_entries": feedback_entries},
    )


@router.get("/diet-chat", response_class=HTMLResponse)
def diet_chat_page(request: Request, db: Session = Depends(get_db)):
    user = get_signed_in_user(request, db)
    if not user:
        return sign_in_redirect()
    messages = (
        db.query(DietChatMessage)
        .filter(DietChatMessage.user_id == user.id)
        .order_by(DietChatMessage.id.desc())
        .limit(40)
        .all()
    )
    messages.reverse()
    return templates.TemplateResponse(
        request=request,
        name="diet_chat.html",
        context={
            "user": user,
            "messages": messages,
            "reply_mode": request.query_params.get("reply"),
        },
    )


@router.post("/diet-chat")
def send_diet_chat_message(
    request: Request,
    message: str = Form(..., min_length=1, max_length=1200),
    db: Session = Depends(get_db),
):
    user = get_signed_in_user(request, db)
    if not user:
        return sign_in_redirect()
    clean_message = message.strip()
    if not clean_message:
        return RedirectResponse(url="/diet-chat?error=empty", status_code=303)

    recent_messages = (
        db.query(DietChatMessage)
        .filter(DietChatMessage.user_id == user.id)
        .order_by(DietChatMessage.id.desc())
        .limit(12)
        .all()
    )
    history = [(item.role, item.content) for item in reversed(recent_messages)]
    history.append(("user", clean_message))
    reply, used_ai = generate_diet_reply(history)

    db.add_all([
        DietChatMessage(user_id=user.id, role="user", content=clean_message),
        DietChatMessage(user_id=user.id, role="assistant", content=reply),
    ])
    db.commit()
    return RedirectResponse(
        url=f"/diet-chat?reply={'ai' if used_ai else 'fallback'}",
        status_code=303,
    )


@router.post("/diet-chat/clear")
def clear_diet_chat(request: Request, db: Session = Depends(get_db)):
    user = get_signed_in_user(request, db)
    if not user:
        return sign_in_redirect()
    db.query(DietChatMessage).filter(DietChatMessage.user_id == user.id).delete()
    db.commit()
    return RedirectResponse(url="/diet-chat?cleared=1", status_code=303)
