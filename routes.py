"""FastAPI endpoints for member authentication, workout plans, and feedback."""

import json
import hashlib
import hmac
import logging
import os
import re
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode

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
from app.models import PasswordResetToken, PendingRegistration
from app.password_reset import send_password_reset_email
from app.updated_plan import generate_updated_plan
from app.verification import (
    check_mobile_code,
    mobile_otp_required,
    send_mobile_code,
    sms_verification_configured,
    turnstile_required,
    turnstile_site_key,
    verify_human,
)

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
REGISTRATION_CODE_LIFETIME = timedelta(minutes=10)
PHONE_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")


def get_signed_in_user(request: Request, db: Session) -> User | None:
    user_id = request.session.get("user_id")
    if not isinstance(user_id, int):
        return None
    return db.query(User).filter(User.id == user_id).first()


def sign_in_redirect() -> RedirectResponse:
    return RedirectResponse(url="/login?error=required", status_code=303)


def _get_valid_password_reset(
    db: Session, email: str, code: str
) -> PasswordResetToken | None:
    if not re.fullmatch(r"\d{6}", code):
        return None
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None
    records = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > datetime.utcnow(),
        )
        .order_by(PasswordResetToken.created_at.desc())
        .limit(5)
        .all()
    )
    if not records:
        return None
    record = records[0]
    record.attempts = (record.attempts or 0) + 1
    if record.attempts > 5:
        record.used_at = datetime.utcnow()
        db.commit()
        return None
    db.commit()
    if record.token_salt:
        digest = hashlib.sha256((record.token_salt + code).encode("utf-8")).hexdigest()
        if hmac.compare_digest(record.token_digest, digest):
            return record
    return None


def _auth_context(**context):
    site_key = turnstile_site_key()
    secret_key = os.getenv("TURNSTILE_SECRET_KEY", "").strip()
    return {
        "turnstile_site_key": site_key if site_key and secret_key else "",
        "require_turnstile": turnstile_required() or bool(site_key or secret_key),
        "require_mobile_otp": mobile_otp_required(),
        **context,
    }


def _normalized_phone(phone: str) -> str:
    compact = re.sub(r"[\s().-]", "", phone.strip())
    if compact.startswith("00"):
        compact = "+" + compact[2:]
    return compact


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    if get_signed_in_user(request, db):
        return RedirectResponse(url="/", status_code=303)

    errors = {
        "invalid": "That email and password don't match.",
        "required": "Please sign in to continue.",
        "human": "Complete the human verification check and try again.",
        "sms": "We could not send the sign-in code to your verified mobile. Please try again.",
    }
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context=_auth_context(
            error=errors.get(request.query_params.get("error", "")),
            notice="Your password has been reset. Sign in with your new password."
            if request.query_params.get("reset") == "1"
            else None,
        ),
    )


@router.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="forgot_password.html",
        context=_auth_context(
            submitted=request.query_params.get("submitted") == "1",
            email=request.query_params.get("email", ""),
            error="Complete the human verification check and try again."
            if request.query_params.get("error") == "human"
            else None,
        ),
    )


@router.post("/forgot-password")
def request_password_reset(
    request: Request,
    email: str = Form(..., min_length=3, max_length=254),
    turnstile_token: str | None = Form(None, alias="cf-turnstile-response"),
    db: Session = Depends(get_db),
):
    if not verify_human(
        turnstile_token,
        request.client.host if request.client else None,
    ):
        return RedirectResponse(url="/forgot-password?error=human", status_code=303)
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
            raw_token = f"{secrets.randbelow(1_000_000):06d}"
            salt = secrets.token_hex(16)
            token_record = PasswordResetToken(
                user_id=user.id,
                token_digest=hashlib.sha256((salt + raw_token).encode("utf-8")).hexdigest(),
                token_salt=salt,
                expires_at=now + PASSWORD_RESET_LIFETIME,
            )
            db.add(token_record)
            db.commit()
            send_password_reset_email(user.email, raw_token)
        else:
            db.rollback()

    return RedirectResponse(
        url=f"/forgot-password?{urlencode({'submitted': 1, 'email': normalized_email})}",
        status_code=303,
    )


@router.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="reset_password.html",
        context=_auth_context(
            email=request.query_params.get("email", ""),
            error=None,
        ),
    )


@router.post("/reset-password", response_class=HTMLResponse)
def reset_password(
    request: Request,
    email: str = Form(..., min_length=3, max_length=254),
    token: str = Form(..., min_length=6, max_length=6),
    password: str = Form(..., min_length=10, max_length=128),
    password_confirm: str = Form(..., max_length=128),
    db: Session = Depends(get_db),
):
    normalized_email = email.strip().casefold()
    reset_record = _get_valid_password_reset(db, normalized_email, token)
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
            context=_auth_context(
                email=normalized_email,
                error=error or "The code is invalid or expired. Request a new one.",
            ),
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
    turnstile_token: str | None = Form(None, alias="cf-turnstile-response"),
    db: Session = Depends(get_db),
):
    if not verify_human(
        turnstile_token,
        request.client.host if request.client else None,
    ):
        return RedirectResponse(url="/login?error=human", status_code=303)
    normalized_email = email.strip().casefold()
    user = db.query(User).filter(User.email == normalized_email).first()
    if not user or not verify_password(password, user.password_hash):
        return RedirectResponse(url="/login?error=invalid", status_code=303)

    mobile_required = mobile_otp_required()
    if mobile_required and not sms_verification_configured():
        return RedirectResponse(url="/login?error=sms", status_code=303)
    if user.mobile_phone:
        try:
            send_mobile_code(user.mobile_phone)
        except RuntimeError:
            return RedirectResponse(url="/login?error=sms", status_code=303)
        request.session.clear()
        request.session["pending_login_user_id"] = user.id
        request.session["pending_mobile_sent_at"] = datetime.utcnow().timestamp()
        return RedirectResponse(url="/verify-mobile", status_code=303)
    if mobile_required:
        request.session.clear()
        request.session["pending_mobile_setup_user_id"] = user.id
        return RedirectResponse(url="/verify-mobile/enroll", status_code=303)

    request.session.clear()
    request.session["user_id"] = user.id
    request.session["just_signed_in"] = True
    return RedirectResponse(url="/", status_code=303)


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, db: Session = Depends(get_db)):
    if get_signed_in_user(request, db):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context=_auth_context(error=None),
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
    mobile_phone: str = Form(""),
    turnstile_token: str | None = Form(None, alias="cf-turnstile-response"),
    db: Session = Depends(get_db),
):
    if not verify_human(
        turnstile_token,
        request.client.host if request.client else None,
    ):
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context=_auth_context(error="Complete the human verification check and try again."),
            status_code=400,
        )
    normalized_email = email.strip().casefold()
    display_name = name.strip()
    phone = _normalized_phone(mobile_phone)
    mobile_required = mobile_otp_required()
    if not display_name:
        error = "Please enter your name."
    elif not EMAIL_PATTERN.fullmatch(normalized_email):
        error = "Enter a valid email address."
    elif password != password_confirm:
        error = "Those passwords don't match."
    elif fitness_goal not in GOALS or workout_intensity not in INTENSITIES:
        error = "Choose a valid fitness goal and training intensity."
    elif mobile_phone.strip() and not PHONE_PATTERN.fullmatch(phone):
        error = "Enter a mobile number with country code, such as +14155552671."
    elif mobile_required and not phone:
        error = "Enter a mobile number to verify your account."
    elif phone and not sms_verification_configured():
        error = "Mobile verification is not configured yet. Leave the phone field blank or try later."
    elif db.query(User).filter(User.email == normalized_email).first():
        error = "That email is already registered. Please sign in or use another."
    else:
        if phone:
            challenge_id = secrets.token_urlsafe(32)
            db.query(PendingRegistration).filter(
                PendingRegistration.expires_at <= datetime.utcnow()
            ).delete(synchronize_session=False)
            db.query(PendingRegistration).filter(
                PendingRegistration.email == normalized_email
            ).delete(synchronize_session=False)
            pending = PendingRegistration(
                id=challenge_id,
                user_id=f"FB{secrets.token_hex(8).upper()}",
                email=normalized_email,
                phone=phone,
                name=display_name,
                age=age,
                weight=weight,
                fitness_goal=fitness_goal,
                workout_intensity=workout_intensity,
                password_hash=hash_password(password),
                expires_at=datetime.utcnow() + REGISTRATION_CODE_LIFETIME,
            )
            db.add(pending)
            try:
                send_mobile_code(phone)
                db.commit()
            except (RuntimeError, IntegrityError):
                db.rollback()
                error = "We could not start mobile verification. Please try again."
            else:
                request.session.clear()
                request.session["pending_registration_id"] = challenge_id
                request.session["pending_mobile_sent_at"] = datetime.utcnow().timestamp()
                return RedirectResponse(url="/verify-mobile", status_code=303)
        if phone:
            return templates.TemplateResponse(
                request=request,
                name="register.html",
                context=_auth_context(error=error),
                status_code=400,
            )
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
            request.session["just_signed_in"] = True
            return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context=_auth_context(error=error),
        status_code=400,
    )


@router.get("/verify-mobile", response_class=HTMLResponse)
def verify_mobile_page(request: Request):
    login_id = request.session.get("pending_login_user_id")
    registration_id = request.session.get("pending_registration_id")
    enroll_phone = request.session.get("pending_mobile_enroll_phone")
    if not login_id and not registration_id and not enroll_phone:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="verify_mobile.html",
        context={
            "purpose": "login" if login_id else "registration" if registration_id else "enrollment",
            "error": None,
        },
    )


@router.post("/verify-mobile")
def verify_mobile(
    request: Request,
    code: str = Form(..., min_length=6, max_length=6),
    db: Session = Depends(get_db),
):
    if not re.fullmatch(r"\d{6}", code):
        purpose = (
            "login"
            if request.session.get("pending_login_user_id")
            else "registration"
            if request.session.get("pending_registration_id")
            else "enrollment"
        )
        return templates.TemplateResponse(
            request=request,
            name="verify_mobile.html",
            context={"purpose": purpose, "error": "Enter the six-digit code from the SMS."},
            status_code=400,
        )

    user_id = request.session.get("pending_login_user_id")
    if isinstance(user_id, int):
        sent_at = request.session.get("pending_mobile_sent_at")
        if (
            not isinstance(sent_at, (int, float))
            or datetime.utcnow().timestamp() - sent_at > REGISTRATION_CODE_LIFETIME.total_seconds()
        ):
            request.session.clear()
            return RedirectResponse(url="/login?error=sms", status_code=303)
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.mobile_phone:
            request.session.clear()
            return RedirectResponse(url="/login?error=invalid", status_code=303)
        try:
            approved = check_mobile_code(user.mobile_phone, code)
        except RuntimeError:
            approved = False
            error = "The mobile verification service is unavailable. Please try again."
        else:
            error = "That code is incorrect or expired. Request a new sign-in code."
        if not approved:
            return templates.TemplateResponse(
                request=request,
                name="verify_mobile.html",
                context={"purpose": "login", "error": error},
                status_code=400,
            )
        request.session.clear()
        request.session["user_id"] = user.id
        request.session["just_signed_in"] = True
        return RedirectResponse(url="/", status_code=303)

    enroll_phone = request.session.get("pending_mobile_enroll_phone")
    if isinstance(enroll_phone, str):
        sent_at = request.session.get("pending_mobile_sent_at")
        if (
            not isinstance(sent_at, (int, float))
            or datetime.utcnow().timestamp() - sent_at > REGISTRATION_CODE_LIFETIME.total_seconds()
        ):
            request.session.pop("pending_mobile_enroll_phone", None)
            request.session.pop("pending_mobile_sent_at", None)
            return RedirectResponse(url="/verify-mobile/enroll?error=expired", status_code=303)
        setup_user_id = request.session.get("pending_mobile_setup_user_id")
        user = (
            db.query(User).filter(User.id == setup_user_id).first()
            if isinstance(setup_user_id, int)
            else get_signed_in_user(request, db)
        )
        if not user:
            request.session.clear()
            return RedirectResponse(url="/login", status_code=303)
        try:
            approved = check_mobile_code(enroll_phone, code)
        except RuntimeError:
            approved = False
            error = "The mobile verification service is unavailable. Please try again."
        else:
            error = "That code is incorrect or expired. Start again to request a new code."
        if not approved:
            return templates.TemplateResponse(
                request=request,
                name="verify_mobile.html",
                context={"purpose": "enrollment", "error": error},
                status_code=400,
            )
        user.mobile_phone = enroll_phone
        db.commit()
        if isinstance(setup_user_id, int):
            request.session.clear()
            request.session["user_id"] = user.id
            request.session["just_signed_in"] = True
        else:
            request.session.pop("pending_mobile_enroll_phone", None)
            request.session.pop("pending_mobile_sent_at", None)
        return RedirectResponse(url="/", status_code=303)

    challenge_id = request.session.get("pending_registration_id")
    pending = (
        db.query(PendingRegistration)
        .filter(
            PendingRegistration.id == challenge_id,
            PendingRegistration.expires_at > datetime.utcnow(),
        )
        .first()
        if isinstance(challenge_id, str)
        else None
    )
    if not pending:
        request.session.clear()
        return RedirectResponse(url="/register", status_code=303)
    try:
        approved = check_mobile_code(pending.phone, code)
    except RuntimeError:
        approved = False
        error = "The mobile verification service is unavailable. Please try again."
    else:
        error = "That code is incorrect or expired. Start again to request a new code."
    if not approved:
        return templates.TemplateResponse(
            request=request,
            name="verify_mobile.html",
            context={"purpose": "registration", "error": error},
            status_code=400,
        )
    user = User(
        user_id=pending.user_id,
        email=pending.email,
        mobile_phone=pending.phone,
        name=pending.name,
        age=pending.age,
        weight=pending.weight,
        fitness_goal=pending.fitness_goal,
        workout_intensity=pending.workout_intensity,
        password_hash=pending.password_hash,
    )
    db.add(user)
    db.delete(pending)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        request.session.clear()
        return RedirectResponse(url="/login?error=invalid", status_code=303)
    request.session.clear()
    request.session["user_id"] = user.id
    request.session["just_signed_in"] = True
    return RedirectResponse(url="/", status_code=303)


@router.get("/verify-mobile/enroll", response_class=HTMLResponse)
def enroll_mobile_page(request: Request, db: Session = Depends(get_db)):
    user = get_signed_in_user(request, db)
    setup_user_id = request.session.get("pending_mobile_setup_user_id")
    if not user and isinstance(setup_user_id, int):
        user = db.query(User).filter(User.id == setup_user_id).first()
    if not user:
        return sign_in_redirect()
    if user.mobile_phone and request.session.get("pending_mobile_setup_user_id") is None:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="enroll_mobile.html",
        context={
            "error": "That verification code expired. Please request a new one."
            if request.query_params.get("error") == "expired"
            else None
        },
    )


@router.post("/verify-mobile/enroll", response_class=HTMLResponse)
def enroll_mobile(
    request: Request,
    mobile_phone: str = Form(..., min_length=8, max_length=24),
    db: Session = Depends(get_db),
):
    user = get_signed_in_user(request, db)
    setup_user_id = request.session.get("pending_mobile_setup_user_id")
    if not user and isinstance(setup_user_id, int):
        user = db.query(User).filter(User.id == setup_user_id).first()
    if not user:
        return sign_in_redirect()
    phone = _normalized_phone(mobile_phone)
    error = None
    if user.mobile_phone and request.session.get("pending_mobile_setup_user_id") is None:
        return RedirectResponse(url="/", status_code=303)
    if not PHONE_PATTERN.fullmatch(phone):
        error = "Enter a mobile number with country code, such as +14155552671."
    elif not sms_verification_configured():
        error = "Mobile verification is not configured yet. Please try later."
    else:
        try:
            send_mobile_code(phone)
        except RuntimeError:
            error = "We could not send a code to that number. Check it and try again."
        else:
            request.session["pending_mobile_enroll_phone"] = phone
            request.session["pending_mobile_sent_at"] = datetime.utcnow().timestamp()
            return RedirectResponse(url="/verify-mobile", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="enroll_mobile.html",
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
        context={
            "user": user,
            "welcome_animation": request.session.pop("just_signed_in", False) is True,
            "sms_verification_available": sms_verification_configured(),
        },
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
