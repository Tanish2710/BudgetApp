"""
auth.py - Accounts, passwords and login sessions.

Passwords are stored as salted PBKDF2-HMAC-SHA256 hashes (never in plain text). A login
creates a random session token; the browser keeps it in a cookie and the database keeps
only its SHA-256, so a copy of the database can't be used to log in.
"""
import base64
import hashlib
import hmac
import re
import secrets
import threading
import time

import database as db

PBKDF2_ITERATIONS = 600_000
MIN_PASSWORD_LENGTH = 8
SESSION_DAYS = 30
EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

# Brute-force guard: after MAX_FAILURES wrong passwords for one email, wait LOCK_SECONDS.
MAX_FAILURES = 5
LOCK_SECONDS = 300
_failures = {}
_failures_lock = threading.Lock()


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERATIONS, base64.b64encode(salt).decode(), base64.b64encode(digest).decode())


def verify_password(password, stored):
    try:
        algo, iterations, salt_b64, digest_b64 = (stored or "").split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), base64.b64decode(salt_b64), int(iterations))
        return hmac.compare_digest(digest, base64.b64decode(digest_b64))
    except (ValueError, TypeError):
        return False


# A real hash to check against when the email is unknown, so a wrong email takes as long as
# a wrong password and response times don't reveal which emails have accounts.
_DUMMY_HASH = hash_password(secrets.token_hex(8))


def password_problem(password, confirm=None):
    """A message describing what's wrong with a new password, or None."""
    if len(password or "") < MIN_PASSWORD_LENGTH:
        return f"Use at least {MIN_PASSWORD_LENGTH} characters for the password."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Use at least one letter and one number in the password."
    if confirm is not None and password != confirm:
        return "The two passwords don't match."
    return None


def clean_email(email):
    """(normalised email, error message or None)."""
    e = str(email or "").strip().lower()
    if not e:
        return e, "Enter your email address."
    if not EMAIL_RE.match(e):
        return e, f"'{e}' doesn't look like an email address."
    return e, None


def sign_up(name, email, password, confirm):
    """Create an account. Returns (account, error)."""
    name = str(name or "").strip()
    if not name:
        return None, "Enter your name."
    email, err = clean_email(email)
    if err:
        return None, err
    err = password_problem(password, confirm)
    if err:
        return None, err
    if db.count_accounts() and not db.get_setting("signups_open", True):
        return None, "New sign-ups are turned off. Ask an admin to turn them back on."
    try:
        uid, _ = db.create_account(name, email, hash_password(password))
    except ValueError as e:
        return None, str(e)
    db.touch_last_login(uid)
    return db.get_user(uid), None


def log_in(email, password):
    """Check credentials. Returns (account, error)."""
    email, err = clean_email(email)
    if err:
        return None, err
    with _failures_lock:
        count, since = _failures.get(email, (0, 0.0))
        if count >= MAX_FAILURES and time.time() - since < LOCK_SECONDS:
            wait = int((LOCK_SECONDS - (time.time() - since)) / 60) + 1
            return None, f"Too many attempts. Try again in {wait} minute{'s' if wait != 1 else ''}."
    account = db.get_account_by_email(email)
    ok = verify_password(password or "", account["password_hash"] if account else _DUMMY_HASH)
    if not (account and ok):
        with _failures_lock:
            count, since = _failures.get(email, (0, 0.0))
            if time.time() - since >= LOCK_SECONDS:
                count = 0
            _failures[email] = (count + 1, time.time())
        return None, "That email and password don't match an account."
    with _failures_lock:
        _failures.pop(email, None)
    if not account["is_active"]:
        return None, "This account has been deactivated. Ask an admin to reactivate it."
    db.touch_last_login(account["user_id"])
    return account, None


def change_password(user_id, current, new, confirm):
    """Returns an error message, or None when the password was changed."""
    account = db.get_user(user_id)
    if not account or not verify_password(current or "", account["password_hash"]):
        return "Your current password isn't right."
    err = password_problem(new, confirm)
    if err:
        return err
    db.set_password_hash(user_id, hash_password(new))
    return None


def _token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def start_session(user_id):
    """Create a login session and return the token to store in the browser."""
    token = secrets.token_urlsafe(32)
    db.create_session(_token_hash(token), user_id, SESSION_DAYS)
    return token


def account_for_token(token):
    if not token:
        return None
    return db.get_session_user(_token_hash(token))


def end_session(token):
    if token:
        db.delete_session(_token_hash(token))
