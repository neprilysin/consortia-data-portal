import hashlib
import os
import secrets
from dotenv import load_dotenv
from fastapi import Request

load_dotenv()

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")


def get_current_email(request: Request) -> str | None:
    return request.cookies.get("email")


def is_admin(email: str | None) -> bool:
    return email is not None and email.lower() == ADMIN_EMAIL.lower()


def get_admin_email() -> str:
    return ADMIN_EMAIL


def get_admin_password() -> str:
    return ADMIN_PASSWORD


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000)
    return f"{salt}${digest.hex()}"


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        salt, hash_hex = stored_hash.split("$", 1)
    except ValueError:
        return False
    expected = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000).hex()
    return secrets.compare_digest(expected, hash_hex)


def verify_admin_password(password: str) -> bool:
    return secrets.compare_digest(password, get_admin_password())
