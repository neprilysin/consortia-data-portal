from fastapi import Request

ADMIN_EMAIL = "admin@example.com"


def get_current_email(request: Request) -> str:
    return request.cookies.get("email", "user@example.com")


def is_admin(email: str) -> bool:
    return email == ADMIN_EMAIL
