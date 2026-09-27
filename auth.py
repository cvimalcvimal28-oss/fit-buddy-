"""Password hashing helpers for FitBuddy member accounts."""

import hashlib
import hmac
import secrets

PBKDF2_ITERATIONS = 310_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded_hash: str | None) -> bool:
    if not encoded_hash:
        return False

    try:
        algorithm, iterations, salt_hex, digest_hex = encoded_hash.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        rounds = int(iterations)
        if rounds < 1 or rounds > 1_000_000:
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (ValueError, TypeError):
        return False

    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return hmac.compare_digest(actual, expected)
