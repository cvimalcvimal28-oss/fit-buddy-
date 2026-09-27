"""FastAPI endpoints for member authentication, workout plans, and feedback."""

import json
import re
import secrets

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import hash_password, verify_password
from app.database import get_db
from app.gemini_flash_generator import generate_nutrition_tip
from app.gemini_generator import generate_workout_plan
from app.models import User, UserFeedback, WorkoutPlan
from app.updated_plan import generate_updated_plan

router = APIRouter()
templates = Jinja2Templates(directory="templates")

GOALS = {"Weight Loss", "Muscle Gain", "General Wellness"}
INTENSITIES = {"Low", "Medium", "High"}
FEEDBACK_CATEGORIES = {"Workout plan", "Website experience", "Gemini AI", "Other"}
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def get_signed_in_user(request: Request, db: Session) -> User | None:
    user_id = request.session.get("user_id")
    if not isinstance(user_id, int):
        return None
    return db.query(User).filter(User.id == user_id).first()


def sign_in_redirect() -> RedirectResponse:
    return RedirectResponse(url="/login?error=required", status_code=303)


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
        context={"error": errors.get(request.query_params.get("error", ""))},
    )


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

