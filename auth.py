from db import get_conn
from utils import hash_password, has_special_char
import os
import secrets
import time
import smtplib
from email.mime.text import MIMEText

RESERVED_USERNAMES = {"admin", "administrator", "root", "system"}
MAX_LOGIN_ATTEMPTS = 3
LOCKOUT_SECONDS = 120


def register_user(email, username, password):
    """Returns (True, None) on success or (False, error_message) on failure."""
    # Basic required fields and password strength checks.
    if not email or not username or not password:
        return False, "All fields are required."
    if username.lower() in RESERVED_USERNAMES:
        return False, "That username is reserved. Please choose another."
    if len(password) < 8:
        return False, "Password must be at least 8 characters."
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit."
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter."
    if not has_special_char(password):
        return False, "Password must contain at least one special character."

    filepath = os.path.join(os.path.dirname(__file__), "rockyou.txt")
    try:
        # Block commonly used passwords from the local wordlist.
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if password.strip() == line.strip():
                    return False, "That password is too common. Please choose a stronger one."
    except FileNotFoundError:
        pass

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    if cursor.fetchone():
        conn.close()
        return False, "An account with that email already exists."
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    if cursor.fetchone():
        conn.close()
        return False, "Username already taken. Please choose another."

    hashed = hash_password(password)
    # New users are non-admin by default.
    cursor.execute(
        "INSERT INTO users (username, password, is_admin, email) VALUES (?, ?, 0, ?)",
        (username, hashed, email),
    )
    conn.commit()
    conn.close()
    return True, None


def login_user(username, password):
    """Returns (username, None) on success or (None, error_message) on failure."""
    # Validate input before any database work.
    if not username or not password:
        return None, "Please enter your username and password."

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT password, failed_attempts, lock_until FROM users WHERE username = ?",
        (username,),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None, "Invalid username or password."

    if row["lock_until"] and int(time.time()) < row["lock_until"]:
        conn.close()
        return None, "Account is temporarily locked. Please try again in a few minutes."

    # Track failed attempts and lock account after too many tries.
    if row["password"] != hash_password(password):
        new_attempts = (row["failed_attempts"] or 0) + 1
        lock_until = int(time.time()) + LOCKOUT_SECONDS if new_attempts >= MAX_LOGIN_ATTEMPTS else None
        cursor.execute(
            "UPDATE users SET failed_attempts = ?, lock_until = ? WHERE username = ?",
            (new_attempts, lock_until, username),
        )
        conn.commit()
        conn.close()
        if lock_until:
            return None, "Too many failed attempts. Account locked for 2 minutes."
        remaining = MAX_LOGIN_ATTEMPTS - new_attempts
        return None, f"Invalid username or password. {remaining} attempt(s) left."

    cursor.execute(
        "UPDATE users SET last_login = ?, failed_attempts = 0, lock_until = NULL WHERE username = ?",
        (int(time.time()), username),
    )
    conn.commit()
    conn.close()
    return username, None


def request_password_reset(email):
    """Sends a reset link if the email exists. Always returns True to avoid leaking info."""
    # Always return success message to prevent account enumeration.
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE email = ?", (email,))
    result = cursor.fetchone()
    if not result:
        conn.close()
        return True
    token = secrets.token_urlsafe(32)
    # Token stays valid for one hour.
    expiry = int(time.time()) + 3600
    cursor.execute(
        "UPDATE users SET reset_token = ?, reset_expiry = ? WHERE email = ?",
        (token, expiry, email),
    )
    conn.commit()
    conn.close()
    _send_reset_email(email, token)
    return True


def reset_password_token(token, new_password):
    """Returns (True, None) on success or (False, error_message) on failure."""
    # Validate token and expiry before updating password.
    if not token:
        return False, "Invalid or expired reset link."
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT email, reset_expiry FROM users WHERE reset_token = ?", (token,)
    )
    result = cursor.fetchone()
    if not result:
        conn.close()
        return False, "Invalid or expired reset link."
    if int(time.time()) > result["reset_expiry"]:
        conn.close()
        return False, "Reset link has expired. Please request a new one."
    if len(new_password) < 8:
        conn.close()
        return False, "Password must be at least 8 characters."
    hashed = hash_password(new_password)
    cursor.execute(
        "UPDATE users SET password = ?, reset_token = NULL, reset_expiry = NULL WHERE email = ?",
        (hashed, result["email"]),
    )
    conn.commit()
    conn.close()
    return True, None


def _send_reset_email(email, token):
    # Email sending is optional and only works when env vars are set.
    sender = os.environ.get("EMAIL_SENDER", "")
    password = os.environ.get("EMAIL_APP_PASSWORD", "")
    if not sender or not password:
        return
    try:
        # Any SMTP error is swallowed to avoid crashing request flow.
        reset_link = f"http://localhost:5000/reset-password?token={token}"
        msg = MIMEText(
            f"Click the link below to reset your password:\n\n{reset_link}\n\nThis link expires in 1 hour."
        )
        msg["Subject"] = "Password Reset Request"
        msg["From"] = sender
        msg["To"] = email
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.send_message(msg)
    except Exception:
        pass

