"""
auth.py - Accounts, passwords and login sessions.

Passwords are stored as salted PBKDF2-HMAC-SHA256 hashes (never in plain text). New
accounts (and changed login emails) only take effect once the owner enters a 6-digit code
sent to that address, so nobody can sign up with an email they don't control. A login
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
from datetime import datetime, timedelta

import database as db
import reminders

PBKDF2_ITERATIONS = 600_000
MIN_PASSWORD_LENGTH = 8
SESSION_DAYS = 30
EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

# Brute-force guard: after MAX_FAILURES wrong passwords for one email, wait LOCK_SECONDS.
CODE_MINUTES = 15          # an emailed code is valid this long
CODE_MAX_ATTEMPTS = 5      # wrong guesses before the code stops working
RESEND_SECONDS = 60        # minimum gap between codes to the same address

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


def email_ready():
    """Verification codes go out through the app's SMTP settings (Reminders > Email delivery
    or the SMTP_* environment variables)."""
    return reminders.smtp_is_configured()


def _new_code():
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires = (datetime.now() + timedelta(minutes=CODE_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")
    return code, _code_hash(code), expires


def _code_hash(code):
    return hashlib.sha256(("sb-verify:" + str(code).strip()).encode("utf-8")).hexdigest()


def _send_code(email, code, name=""):
    hello = f"Hi {name.split()[0]}," if name else "Hi,"
    plain = (f"{hello}\n\nYour {reminders.APP_NAME} verification code is: {code}\n\n"
             f"It expires in {CODE_MINUTES} minutes. If you didn't ask for this, you can ignore this email.\n")
    html_body = (f"<div style='font-family:Inter,Arial,sans-serif;color:#2b2d42;max-width:420px'>"
                 f"<p>{hello}</p><p>Your {reminders.APP_NAME} verification code is:</p>"
                 f"<p style='font-size:28px;font-weight:700;letter-spacing:6px;margin:12px 0'>{code}</p>"
                 f"<p style='color:#80849a;font-size:13px'>It expires in {CODE_MINUTES} minutes. "
                 f"If you didn't ask for this, you can ignore this email.</p></div>")
    return reminders.send_email(email, f"{code} is your {reminders.APP_NAME} verification code", plain, html_body,
                                is_dry_run=False)


def start_sign_up(name, email, password, confirm):
    """Check the details and email a verification code. The account is only created once the
    code is entered (see verify_code). Returns (email, error)."""
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
    if db.get_account_by_email(email):
        return None, "An account with this email already exists. Log in instead."
    if not email_ready():
        return None, ("This app can't send email yet, so new accounts can't be verified. "
                      "The person running it needs to set up the email server.")
    code, code_hash, expires = _new_code()
    db.save_pending_verification(email, code_hash, expires, name=name, password_hash=hash_password(password))
    ok, msg = _send_code(email, code, name)
    if not ok:
        db.delete_pending_verification(email)
        return None, "We couldn't send the verification email. Check the address and try again."
    return email, None


def resend_code(email):
    """Email a fresh code for a pending sign-up or email change. Returns an error or None."""
    pending = db.get_pending_verification(email)
    if not pending:
        return "There's nothing waiting to be verified for this email. Start again."
    sent = datetime.strptime(pending["sent_at"], "%Y-%m-%d %H:%M:%S")
    wait = RESEND_SECONDS - int((datetime.now() - sent).total_seconds())
    if wait > 0:
        return f"Wait {wait} seconds before asking for another code."
    code, code_hash, expires = _new_code()
    db.refresh_pending_code(email, code_hash, expires)
    ok, _ = _send_code(email, code, pending.get("name") or "")
    return None if ok else "We couldn't send the email. Try again in a moment."


def verify_code(email, code):
    """Finish a sign-up or email change. Returns (account, error)."""
    pending = db.get_pending_verification(email)
    if not pending:
        return None, "This code has expired. Start again."
    if pending["attempts"] >= CODE_MAX_ATTEMPTS:
        return None, "Too many wrong codes. Ask for a new code."
    if datetime.now() > datetime.strptime(pending["expires_at"], "%Y-%m-%d %H:%M:%S"):
        return None, "This code has expired. Ask for a new code."
    if not hmac.compare_digest(pending["code_hash"], _code_hash(code or "")):
        db.count_pending_attempt(email)
        left = CODE_MAX_ATTEMPTS - pending["attempts"] - 1
        return None, ("That code isn't right." + (f" {left} tries left." if left else " Ask for a new code."))
    try:
        if pending["user_id"]:  # changing the login email of an existing account
            if db.get_user_by_email(pending["email"]) and db.get_user_by_email(pending["email"])["user_id"] != pending["user_id"]:
                raise ValueError("That email is now in use by someone else.")
            db.update_user(pending["user_id"], email=pending["email"])
            uid = pending["user_id"]
        else:
            if db.count_accounts() and not db.get_setting("signups_open", True):
                raise ValueError("New sign-ups were turned off. Ask an admin to turn them back on.")
            uid, _ = db.create_account(pending["name"], pending["email"], pending["password_hash"])
    except ValueError as e:
        db.delete_pending_verification(email)
        return None, str(e)
    db.delete_pending_verification(email)
    db.touch_last_login(uid)
    return db.get_user(uid), None


def start_email_change(user_id, new_email):
    """Email a code to a new login address; the change happens in verify_code. Returns (email, error)."""
    email, err = clean_email(new_email)
    if err:
        return None, err
    other = db.get_user_by_email(email)
    if other and other["user_id"] != user_id:
        return None, f"Email '{email}' is already in use."
    if not email_ready():
        return None, "This app can't send email yet, so a new email can't be verified."
    code, code_hash, expires = _new_code()
    db.save_pending_verification(email, code_hash, expires, name=db.get_user(user_id)["name"], user_id=user_id)
    ok, _ = _send_code(email, code, db.get_user(user_id)["name"])
    if not ok:
        db.delete_pending_verification(email)
        return None, "We couldn't send the verification email. Check the address and try again."
    return email, None


PENDING = "pending"  # log_in's error when the sign-up hasn't been verified yet


def log_in(email, password):
    """Check credentials. Returns (account, error); error is PENDING for an unverified sign-up."""
    email, err = clean_email(email)
    if err:
        return None, err
    with _failures_lock:
        count, since = _failures.get(email, (0, 0.0))
        if count >= MAX_FAILURES and time.time() - since < LOCK_SECONDS:
            wait = int((LOCK_SECONDS - (time.time() - since)) / 60) + 1
            return None, f"Too many attempts. Try again in {wait} minute{'s' if wait != 1 else ''}."
    account = db.get_account_by_email(email)
    if not account:
        pending = db.get_pending_verification(email)
        if pending and not pending["user_id"] and verify_password(password or "", pending["password_hash"]):
            return None, PENDING
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
