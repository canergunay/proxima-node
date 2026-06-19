"""Authentication: password hashing, JWT, Fernet encryption, rate limiting."""

import base64
import hashlib
import os
import secrets
import threading
import time

import jwt
from cryptography.fernet import Fernet, InvalidToken
from werkzeug.security import check_password_hash, generate_password_hash

from core.config import JWT_SECRET_PATH

TOKEN_EXPIRY_DAYS = 90

# ── JWT secret management ────────────────────────────────────────────────

_jwt_secret: str | None = None
_jwt_lock = threading.Lock()


def get_jwt_secret() -> str:
    """Return JWT secret, creating one if it doesn't exist."""
    global _jwt_secret
    if _jwt_secret is not None:
        return _jwt_secret
    with _jwt_lock:
        if _jwt_secret is not None:
            return _jwt_secret
        if os.path.exists(JWT_SECRET_PATH):
            with open(JWT_SECRET_PATH, "r") as f:
                _jwt_secret = f.read().strip()
        else:
            _jwt_secret = secrets.token_hex(32)
            with open(JWT_SECRET_PATH, "w") as f:
                f.write(_jwt_secret)
            os.chmod(JWT_SECRET_PATH, 0o600)
        return _jwt_secret


# ── Password hashing ────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return generate_password_hash(password, method="pbkdf2:sha256")


def verify_password(password: str, password_hash: str) -> bool:
    return check_password_hash(password_hash, password)


# ── JWT tokens ───────────────────────────────────────────────────────────

def create_token(username: str) -> str:
    payload = {
        "sub": username,
        "iat": int(time.time()),
        "exp": int(time.time()) + TOKEN_EXPIRY_DAYS * 86400,
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm="HS256")


def verify_token(token: str) -> dict | None:
    """Return {"username": ...} if valid, else None."""
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=["HS256"])
        username = payload.get("sub")
        if not username:
            return None
        return {"username": username}
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


# ── Fernet encryption (for server credentials) ──────────────────────────

def _get_fernet() -> Fernet:
    """Derive a Fernet key from the JWT secret."""
    key = hashlib.sha256(get_jwt_secret().encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string using Fernet."""
    return _get_fernet().encrypt(plaintext.encode()).decode("ascii")


def decrypt_value(ciphertext: str) -> str | None:
    """Decrypt a string. Returns None if decryption fails."""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode("utf-8")
    except (InvalidToken, Exception):
        return None


# ── Login rate limiting ──────────────────────────────────────────────────

_rate_lock = threading.Lock()
_fail_tracker: dict[str, list[float]] = {}
RATE_WINDOW = 300
MAX_ATTEMPTS = 10
LOCKOUT_SECONDS = 300


def check_rate_limit(ip: str) -> int | None:
    """Check if IP is rate-limited. Returns seconds remaining if locked out."""
    now = time.time()
    with _rate_lock:
        timestamps = _fail_tracker.get(ip, [])
        timestamps = [t for t in timestamps if now - t < RATE_WINDOW + LOCKOUT_SECONDS]
        _fail_tracker[ip] = timestamps
        recent = [t for t in timestamps if now - t < RATE_WINDOW]
        if len(recent) >= MAX_ATTEMPTS:
            last_fail = max(recent)
            remaining = int(LOCKOUT_SECONDS - (now - last_fail))
            return max(remaining, 1)
    return None


def record_login_failure(ip: str) -> None:
    with _rate_lock:
        if ip not in _fail_tracker:
            _fail_tracker[ip] = []
        _fail_tracker[ip].append(time.time())


def clear_login_failures(ip: str) -> None:
    with _rate_lock:
        _fail_tracker.pop(ip, None)
