import hashlib
import secrets
import string
from typing import Tuple

MIN_PASSWORD_LENGTH = 8


def hash_password(password: str) -> str:
    """Return a SHA-256 hash for the provided password."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    """Check if the provided password matches the stored hash."""
    return hash_password(password) == hashed


def has_special_char(password: str) -> bool:
    # True when password contains at least one punctuation symbol.
    return any(char in string.punctuation for char in password)


def generate_token(length: int = 32) -> str:
    # Generate URL-safe token for reset links or similar use.
    return secrets.token_urlsafe(length)


def validate_password(password: str) -> Tuple[bool, str]:
    # Reusable password policy validation helper.
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, "Password must be at least 8 characters long."
    if not any(char.isdigit() for char in password):
        return False, "Password must contain at least one digit."
    if not any(char.isupper() for char in password):
        return False, "Password must contain at least one uppercase letter."
    if not has_special_char(password):
        return False, "Password must contain at least one special character."
    return True, ""