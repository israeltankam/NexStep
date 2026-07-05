"""PIN and password hashing.

The specification asks for searchable PIN lookup plus slow verification hashes.
This module keeps both concerns separate: HMAC for lookup, PBKDF2 for local
verification. If argon2 is installed later, the public API can be upgraded
without changing the database-facing services.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets


PBKDF2_ITERATIONS = 240_000
HASH_PREFIX = "pbkdf2_sha256"


def _pepper() -> str:
    return os.getenv("APP_PIN_PEPPER", "nexstep-local-dev-pepper-change-me")


def _iterations() -> int:
    """Keep production hashes slow while making the 100-test suite practical."""

    return 30_000 if os.getenv("NEXSTEP_FAST_HASH") == "1" else PBKDF2_ITERATIONS


def normalize_pin(pin: str | int | None) -> str:
    return "" if pin is None else str(pin).strip().casefold()


def pin_lookup(pin: str | int | None) -> str:
    """Create the deterministic lookup key used to find orgs and org-user links."""

    return hmac.new(_pepper().encode("utf-8"), normalize_pin(pin).encode("utf-8"), hashlib.sha256).hexdigest()


def _hash_secret(secret: str, *, normalize: bool, peppered: bool) -> str:
    raw = normalize_pin(secret) if normalize else str(secret)
    if peppered:
        raw = f"{raw}{_pepper()}"
    salt = secrets.token_bytes(16)
    iterations = _iterations()
    digest = hashlib.pbkdf2_hmac("sha256", raw.encode("utf-8"), salt, iterations)
    return "$".join(
        [
            HASH_PREFIX,
            str(iterations),
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        ]
    )


def _verify_secret(secret: str, stored_hash: str | None, *, normalize: bool, peppered: bool) -> bool:
    if not stored_hash:
        return False
    try:
        prefix, iterations, salt_b64, digest_b64 = stored_hash.split("$", 3)
        if prefix != HASH_PREFIX:
            return False
        raw = normalize_pin(secret) if normalize else str(secret)
        if peppered:
            raw = f"{raw}{_pepper()}"
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_b64.encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", raw.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def hash_pin(pin: str | int) -> str:
    return _hash_secret(str(pin), normalize=True, peppered=True)


def verify_pin(pin: str | int, stored_hash: str | None) -> bool:
    return _verify_secret(str(pin), stored_hash, normalize=True, peppered=True)


def hash_password(password: str) -> str:
    return _hash_secret(password, normalize=False, peppered=False)


def verify_password(password: str, stored_hash: str | None) -> bool:
    return _verify_secret(password, stored_hash, normalize=False, peppered=False)
