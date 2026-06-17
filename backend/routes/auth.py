"""Authentication routes: register, login, and JWT dependency.

Endpoints
    POST /auth/register  —  Create account.  Hashes password with bcrypt,
                             stores user, returns JWT in httpOnly cookie.
    POST /auth/login     —  Sign in.  Verifies credentials, issues JWT.

Dependency
    get_current_user(db, token)  —  Extracts User from JWT cookie.  Use as
                                    ``Depends(get_current_user)`` in routes
                                    that require authentication.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
import bcrypt
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models import User

# ── Router ─────────────────────────────────────────────
router = APIRouter()


# ── Pydantic Schemas ───────────────────────────────────

class RegisterRequest(BaseModel):
    """Payload for POST /auth/register."""
    email: EmailStr
    password: str  # At least 6 characters (validated at endpoint level)


class LoginRequest(BaseModel):
    """Payload for POST /auth/login."""
    email: EmailStr
    password: str


class UserData(BaseModel):
    """User info returned in API responses (never expose password_hash).

    Field names match the ORM ``User`` model so ``from_attributes=True``
    can hydrate directly from a SQLAlchemy instance.
    """
    id: int
    email: str

    model_config = {"from_attributes": True}


AuthResponse = dict[str, Any]  # {"status": "...", "data": {...}, "message": "..."}


# ── Helpers ────────────────────────────────────────────

def _hash_password(password: str) -> str:
    """Return bcrypt hash of *password*."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches *hashed*."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def _create_jwt(user_id: int, email: str) -> str:
    """Create a signed JWT with ``sub`` = user_id and ``email`` claim.

    Expiry is read from ``settings.jwt_expiry_hours``.
    """
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expiry_hours),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _set_jwt_cookie(response: Response, token: str) -> None:
    """Attach the JWT as an httpOnly cookie to *response*."""
    response.set_cookie(
        key="wutt_token",
        value=token,
        httponly=True,
        secure=not settings.debug,          # secure=True in production (HTTPS only)
        samesite="lax",
        max_age=int(timedelta(hours=settings.jwt_expiry_hours).total_seconds()),
    )


def _ok(data: dict[str, Any], message: str = "") -> AuthResponse:
    """Return the standard success envelope."""
    return {"status": "success", "data": data, "message": message}


def _err(message: str, code: int = 400) -> HTTPException:
    """Return a FastAPI HTTPException in the standard error envelope."""
    return HTTPException(
        status_code=code,
        detail={"status": "error", "data": {}, "message": message},
    )


# ── Dependencies ───────────────────────────────────────

def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Extract and validate the JWT from the ``wutt_token`` cookie.

    Returns the authenticated ``User`` ORM object.

    Usage::

        @router.get("/protected")
        def protected_route(current_user: User = Depends(get_current_user)):
            ...

    Raises:
        HTTPException 401 if the cookie is missing, expired, or the user
        no longer exists.
    """
    token = request.cookies.get("wutt_token")
    if not token:
        raise _err("Authentication required — please log in.", code=401)

    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm],
        )
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise _err("Invalid token — missing subject.", code=401)
    except JWTError:
        raise _err("Invalid or expired token — please log in again.", code=401)

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise _err("User account not found.", code=401)

    return user


# ── Routes ─────────────────────────────────────────────

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    """Create a new user account and sign them in immediately.

    *body* — ``email`` + ``password`` (min 6 chars).
    Returns user data + sets ``wutt_token`` httpOnly cookie.

    Raises:
        400 if email is already registered.
        400 if password is shorter than 6 characters.
    """
    # ── Validate ──────────────────────────────────────
    email = body.email.strip().lower()
    if len(body.password) < 6:
        raise _err("Password must be at least 6 characters.")

    # ── Check uniqueness ──────────────────────────────
    if db.query(User).filter(User.email == email).first():
        raise _err("An account with this email already exists.")

    # ── Create user ───────────────────────────────────
    try:
        user = User(
            email=email,
            password_hash=_hash_password(body.password),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        token = _create_jwt(user.id, user.email)
        _set_jwt_cookie(response, token)

        return _ok(
            data=UserData.model_validate(user).model_dump(),
            message="Account created successfully.",
        )
    except Exception as exc:
        db.rollback()
        raise _err(f"Registration failed — {exc}")


@router.post("/login")
def login(
    body: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    """Sign in with email and password.

    *body* — ``email`` + ``password``.
    Returns user data + sets ``wutt_token`` httpOnly cookie.

    Raises:
        401 if email is not found or password does not match.
    """
    email = body.email.strip().lower()

    user = db.query(User).filter(User.email == email).first()
    if not user or not _verify_password(body.password, user.password_hash):
        raise _err("Invalid email or password.", code=401)

    token = _create_jwt(user.id, user.email)
    _set_jwt_cookie(response, token)

    return _ok(
        data=UserData.model_validate(user).model_dump(),
        message="Logged in successfully.",
    )


@router.get("/me")
def get_me(
    current_user: User = Depends(get_current_user),
) -> AuthResponse:
    """Return the currently authenticated user (from JWT cookie).

    Useful for the frontend to discover the logged-in user's ID
    without hardcoding it.
    """
    return _ok(
        data=UserData.model_validate(current_user).model_dump(),
        message="",
    )
