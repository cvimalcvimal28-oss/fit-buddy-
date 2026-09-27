"""Turnstile and Twilio Verify integrations for account verification."""

import base64
import json
import logging
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


def turnstile_required() -> bool:
    configured = os.getenv("REQUIRE_TURNSTILE")
    if configured is not None:
        return configured.lower() == "true"
    return os.getenv("COOKIE_SECURE", "false").lower() == "true"


def mobile_otp_required() -> bool:
    configured = os.getenv("REQUIRE_MOBILE_OTP")
    if configured is not None:
        return configured.lower() == "true"
    return os.getenv("COOKIE_SECURE", "false").lower() == "true"


def turnstile_site_key() -> str:
    return os.getenv("TURNSTILE_SITE_KEY", "").strip()


def verify_human(token: str | None, remote_ip: str | None) -> bool:
    site_key = turnstile_site_key()
    secret_key = os.getenv("TURNSTILE_SECRET_KEY", "").strip()
    required = turnstile_required()
    if not site_key and not secret_key and not required:
        return True
    if not site_key or not secret_key or not token:
        logger.warning("Human verification failed because its token or server keys are missing.")
        return False

    payload = {"secret": secret_key, "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip
    request = Request(
        "https://challenges.cloudflare.com/turnstile/v0/siteverify",
        data=urlencode(payload).encode("ascii"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=8) as response:
            result = json.loads(response.read(16_384))
    except (HTTPError, URLError, TimeoutError, ValueError, OSError):
        logger.exception("Cloudflare Turnstile verification could not be completed.")
        return False
    return result.get("success") is True


def sms_verification_configured() -> bool:
    return all(
        os.getenv(key, "").strip()
        for key in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_VERIFY_SERVICE_SID")
    )


def _twilio_request(endpoint: str, values: dict[str, str]) -> dict:
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    if not sms_verification_configured():
        raise RuntimeError("SMS verification is not configured.")
    credentials = base64.b64encode(f"{account_sid}:{auth_token}".encode("utf-8")).decode("ascii")
    request = Request(
        endpoint,
        data=urlencode(values).encode("ascii"),
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read(16_384))
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as error:
        logger.exception("Twilio Verify request failed.")
        raise RuntimeError("We could not send or verify the mobile code. Please try again.") from error


def send_mobile_code(phone: str) -> None:
    service_sid = os.getenv("TWILIO_VERIFY_SERVICE_SID", "").strip()
    result = _twilio_request(
        f"https://verify.twilio.com/v2/Services/{service_sid}/Verifications",
        {"To": phone, "Channel": "sms"},
    )
    if result.get("status") not in {"pending", "approved"}:
        logger.error("Twilio Verify did not accept the mobile verification request.")
        raise RuntimeError("We could not send the mobile code. Check the number and try again.")


def check_mobile_code(phone: str, code: str) -> bool:
    service_sid = os.getenv("TWILIO_VERIFY_SERVICE_SID", "").strip()
    result = _twilio_request(
        f"https://verify.twilio.com/v2/Services/{service_sid}/VerificationCheck",
        {"To": phone, "Code": code},
    )
    return result.get("status") == "approved"
