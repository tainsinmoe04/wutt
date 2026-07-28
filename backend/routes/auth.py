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

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import re
import secrets
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
import bcrypt
import httpx
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models import AuthIdentity, User
from services.auth_session_svc import create_session, lookup_session, revoke_session

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

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_PROVIDER = "google"
OAUTH_STATE_COOKIE = "wutt_google_oauth"
GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


# ── Helpers ────────────────────────────────────────────

def _hash_password(password: str) -> str:
    """Return bcrypt hash of *password*."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(plain: str, hashed: str | None) -> bool:
    """Return True if *plain* matches *hashed*."""
    if not hashed:
        return False
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def _is_configured_demo_email(email: str) -> bool:
    """Return whether *email* is the dedicated configured demo identity."""
    configured_email = settings.demo_login_email.strip().lower()
    return bool(configured_email) and secrets.compare_digest(
        email,
        configured_email,
    )


def _matches_configured_demo_login(email: str, password: str) -> bool:
    """Return whether credentials exactly match the enabled demo account."""
    if not settings.demo_login_enabled:
        return False
    configured_password = settings.demo_login_password
    if not configured_password:
        return False
    return (
        _is_configured_demo_email(email)
        and secrets.compare_digest(password, configured_password)
    )


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
    """Attach the JWT as an httpOnly cookie to *response*.

    In production (cross-origin), use SameSite=None + Secure so the cookie
    reaches both the backend domain and any frontend static-site domain.
    In local dev (debug), keep SameSite=Lax for simplicity.
    """
    response.set_cookie(
        key="wutt_token",
        value=token,
        httponly=True,
        secure=not settings.debug,
        samesite="none" if not settings.debug else "lax",
        max_age=int(timedelta(hours=settings.jwt_expiry_hours).total_seconds()),
    )


def _set_session_cookie(response: Response, token: str) -> None:
    """Attach a revocable opaque browser session cookie."""
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=not settings.debug,
        samesite="none" if not settings.debug else "lax",
        max_age=int(timedelta(hours=settings.session_expiry_hours).total_seconds()),
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    """Expire browser authentication cookies using their original attributes."""
    cookie_options = {
        "httponly": True,
        "secure": not settings.debug,
        "samesite": "none" if not settings.debug else "lax",
        "path": "/",
    }
    response.delete_cookie(settings.session_cookie_name, **cookie_options)
    response.delete_cookie("wutt_token", **cookie_options)


def _google_is_configured() -> bool:
    """Return whether the Google web-server flow is fully configured."""
    return bool(
        settings.google_client_id
        and settings.google_client_secret
        and settings.google_redirect_uri
        and settings.frontend_url
    )


def _create_oauth_transaction(state: str, nonce: str, verifier: str) -> str:
    """Sign short-lived OAuth state without exposing its verifier to JavaScript."""
    return jwt.encode(
        {
            "type": "google_oauth",
            "state": state,
            "nonce": nonce,
            "verifier": verifier,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def _decode_oauth_transaction(value: str) -> dict[str, Any]:
    """Validate a signed OAuth transaction cookie."""
    try:
        transaction = jwt.decode(
            value,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise _err("Google sign-in session is invalid or expired.", code=400) from exc
    if transaction.get("type") != "google_oauth":
        raise _err("Google sign-in session is invalid.", code=400)
    return transaction


async def _exchange_google_code(code: str, verifier: str) -> dict[str, Any]:
    """Exchange the authorization code directly with Google's token endpoint."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "code": code,
                    "code_verifier": verifier,
                    "grant_type": "authorization_code",
                    "redirect_uri": settings.google_redirect_uri,
                },
            )
    except httpx.HTTPError as exc:
        raise _err("Google sign-in is temporarily unavailable.", code=502) from exc
    if response.status_code != 200:
        raise _err("Google sign-in could not be completed.", code=401)
    try:
        return response.json()
    except ValueError as exc:
        raise _err("Google returned an invalid token response.", code=502) from exc


def _verify_google_token(encoded_token: str) -> dict[str, Any]:
    """Verify signature, issuer, audience, and expiration using google-auth."""
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token as google_id_token
    except ImportError as exc:
        raise _err("Google authentication support is unavailable.", code=503) from exc
    try:
        claims = google_id_token.verify_oauth2_token(
            encoded_token,
            google_requests.Request(),
            settings.google_client_id,
        )
    except (ValueError, TypeError) as exc:
        raise _err("Google identity verification failed.", code=401) from exc
    return dict(claims)


def _validate_google_claims(
    claims: dict[str, Any],
    expected_nonce: str,
    *,
    now: datetime | None = None,
) -> tuple[str, str]:
    """Validate required OpenID Connect claims and return subject and email."""
    issuer = claims.get("iss")
    audience = claims.get("aud")
    subject = claims.get("sub")
    email = str(claims.get("email", "")).strip().lower()
    expiration = claims.get("exp")

    if issuer not in GOOGLE_ISSUERS:
        raise _err("Google identity issuer is invalid.", code=401)
    if audience != settings.google_client_id:
        raise _err("Google identity audience is invalid.", code=401)
    try:
        expires_at = datetime.fromtimestamp(float(expiration), tz=timezone.utc)
    except (TypeError, ValueError, OverflowError) as exc:
        raise _err("Google identity expiration is invalid.", code=401) from exc
    if expires_at <= (now or datetime.now(timezone.utc)):
        raise _err("Google identity token has expired.", code=401)
    if not subject:
        raise _err("Google identity subject is missing.", code=401)
    if not secrets.compare_digest(str(claims.get("nonce", "")), expected_nonce):
        raise _err("Google identity nonce did not match.", code=401)
    if claims.get("email_verified") is not True:
        raise _err("Google account email is not verified.", code=403)
    if not email:
        raise _err("Google account did not provide an email.", code=400)
    return str(subject), email


def _frontend_redirect(**parameters: str) -> str:
    """Build a redirect only from the configured frontend URL."""
    parts = urlsplit(settings.frontend_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update(parameters)
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )


def _clear_oauth_cookie(response: Response) -> None:
    """Delete the short-lived OAuth transaction cookie."""
    response.delete_cookie(
        OAUTH_STATE_COOKIE,
        httponly=True,
        secure=not settings.debug,
        samesite="lax",
        path="/",
    )


def _resolve_google_user(
    db: Session,
    *,
    subject: str,
    email: str,
) -> User:
    """Safely resolve, link, or create a user for a verified Google identity."""
    now = datetime.now(timezone.utc)
    identity = (
        db.query(AuthIdentity)
        .filter(
            AuthIdentity.provider == GOOGLE_PROVIDER,
            AuthIdentity.provider_subject == subject,
        )
        .first()
    )
    if identity is not None:
        user = db.query(User).filter(User.id == identity.user_id).first()
        if user is None:
            raise _err("Google identity is linked to a missing account.", code=409)
        email_owner = db.query(User).filter(User.email == email).first()
        if email_owner is not None and email_owner.id != user.id:
            raise _err("Google identity conflicts with another account.", code=409)
        identity.provider_email = email
        identity.email_verified = True
        identity.last_used_at = now
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
        return user

    user = db.query(User).filter(User.email == email).first()
    if user is not None:
        other_google_identity = (
            db.query(AuthIdentity)
            .filter(
                AuthIdentity.user_id == user.id,
                AuthIdentity.provider == GOOGLE_PROVIDER,
            )
            .first()
        )
        if other_google_identity is not None:
            raise _err("Google account conflicts with an existing identity.", code=409)

    try:
        if user is None:
            user = User(email=email, password_hash=None)
            db.add(user)
            db.flush()
        identity = AuthIdentity(
            user_id=user.id,
            provider=GOOGLE_PROVIDER,
            provider_subject=subject,
            provider_email=email,
            email_verified=True,
            created_at=now,
            last_used_at=now,
        )
        db.add(identity)
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError:
        db.rollback()
        # A concurrent callback may have created this exact identity first.
        identity = (
            db.query(AuthIdentity)
            .filter(
                AuthIdentity.provider == GOOGLE_PROVIDER,
                AuthIdentity.provider_subject == subject,
            )
            .first()
        )
        if identity is None:
            raise _err("Google account conflicts with an existing account.", code=409)
        user = db.query(User).filter(User.id == identity.user_id).first()
        if user is None:
            raise _err("Google identity is linked to a missing account.", code=409)
        email_owner = db.query(User).filter(User.email == email).first()
        if email_owner is not None and email_owner.id != user.id:
            raise _err("Google identity conflicts with another account.", code=409)
        return user


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

def _get_user_from_jwt(token: str, db: Session) -> User:
    """Decode a legacy JWT and resolve its current database user."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        subject = payload.get("sub")
        if subject is None:
            raise _err("Invalid token — missing subject.", code=401)
        user_id = int(subject)
    except (JWTError, TypeError, ValueError):
        raise _err("Invalid or expired token — please log in again.", code=401)

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise _err("User account not found.", code=401)
    return user


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Authenticate a browser session or a backward-compatible legacy JWT.

    Precedence is an explicit legacy bearer JWT, then the browser session
    cookie, then the legacy JWT cookie. If a browser session cookie is
    present but invalid, authentication fails closed instead of falling back.

    Returns the authenticated ``User`` ORM object.

    Usage::

        @router.get("/protected")
        def protected_route(current_user: User = Depends(get_current_user)):
            ...

    Raises:
        HTTPException 401 if no valid token is found.
    """
    # 1. Explicit bearer JWT remains backward compatible for API clients.
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return _get_user_from_jwt(auth_header[7:], db)

    # 2. New browser sessions are revocable and fail closed when supplied.
    session_token = request.cookies.get(settings.session_cookie_name)
    if session_token:
        auth_session = lookup_session(db, session_token)
        if auth_session is None:
            raise _err("Invalid or expired session — please log in again.", code=401)
        user = db.query(User).filter(User.id == auth_session.user_id).first()
        if user is None:
            raise _err("User account not found.", code=401)
        return user

    # 3. Existing browser clients still carry the legacy JWT cookie.
    legacy_token = request.cookies.get("wutt_token")
    if legacy_token:
        return _get_user_from_jwt(legacy_token, db)

    raise _err("Authentication required — please log in.", code=401)


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
    if len(body.password) < 8 or not re.search(r'[a-zA-Z]', body.password) or not re.search(r'[0-9]', body.password):
        raise _err("Password must be at least 8 characters and include both letters and numbers.")

    # ── Check uniqueness ──────────────────────────────
    if (
        settings.demo_login_enabled
        and _is_configured_demo_email(email)
    ):
        raise _err("This email is reserved for the configured demo account.", code=409)
    if db.query(User).filter(User.email == email).first():
        raise _err("This email is already registered. Please log in instead.", code=409)

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
            data={
                **UserData.model_validate(user).model_dump(),
                "token": token,
            },
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

    if _is_configured_demo_email(email) and not settings.demo_login_enabled:
        raise _err("Invalid email or password.", code=401)

    user = db.query(User).filter(User.email == email).first()
    password_is_valid = bool(
        user and _verify_password(body.password, user.password_hash)
    )

    if not password_is_valid and _matches_configured_demo_login(
        email,
        body.password,
    ):
        if user is not None:
            # Never use demo mode to take over an existing account.
            raise _err("Invalid email or password.", code=401)
        user = User(
            email=email,
            password_hash=_hash_password(body.password),
        )
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
        except IntegrityError:
            db.rollback()
            raise _err("Invalid email or password.", code=401)
        password_is_valid = True

    if not user or not password_is_valid:
        raise _err("Invalid email or password.", code=401)

    token = _create_jwt(user.id, user.email)
    _set_jwt_cookie(response, token)

    return _ok(
        data={
            **UserData.model_validate(user).model_dump(),
            "token": token,
        },
        message="Logged in successfully.",
    )


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    """Revoke the current browser session and expire all auth cookies."""
    session_token = request.cookies.get(settings.session_cookie_name)
    if session_token:
        revoke_session(db, raw_token=session_token)

    _clear_auth_cookies(response)
    return _ok(data={}, message="Logged out successfully.")


@router.get("/google/start")
def google_start() -> RedirectResponse:
    """Begin Google Authorization Code authentication with PKCE."""
    if not _google_is_configured():
        if settings.frontend_url:
            response = RedirectResponse(
                _frontend_redirect(
                    auth_error="google",
                    auth_reason="configuration",
                ),
                status_code=status.HTTP_302_FOUND,
            )
            response.headers["Cache-Control"] = "no-store"
            return response
        raise _err("Google sign-in is not configured.", code=503)

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    authorization_url = GOOGLE_AUTHORIZE_URL + "?" + urlencode({
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })

    response = RedirectResponse(
        authorization_url,
        status_code=status.HTTP_302_FOUND,
    )
    response.set_cookie(
        key=OAUTH_STATE_COOKIE,
        value=_create_oauth_transaction(state, nonce, verifier),
        httponly=True,
        secure=not settings.debug,
        samesite="lax",
        max_age=600,
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/google/callback")
async def google_callback(
    request: Request,
    db: Session = Depends(get_db),
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> RedirectResponse:
    """Complete Google authentication and issue only a WUTT browser session."""
    if not _google_is_configured():
        raise _err("Google sign-in is not configured.", code=503)

    transaction_cookie = request.cookies.get(OAUTH_STATE_COOKIE)
    if error or not code or not state or not transaction_cookie:
        response = RedirectResponse(
            _frontend_redirect(auth_error="google"),
            status_code=status.HTTP_302_FOUND,
        )
        _clear_oauth_cookie(response)
        response.headers["Cache-Control"] = "no-store"
        return response

    transaction = _decode_oauth_transaction(transaction_cookie)
    expected_state = str(transaction.get("state", ""))
    if not expected_state or not secrets.compare_digest(expected_state, state):
        raise _err("Google sign-in state did not match.", code=400)

    token_response = await _exchange_google_code(
        code,
        str(transaction.get("verifier", "")),
    )
    encoded_id_token = token_response.get("id_token")
    if not isinstance(encoded_id_token, str) or not encoded_id_token:
        raise _err("Google did not return an identity token.", code=401)

    claims = _verify_google_token(encoded_id_token)
    subject, email = _validate_google_claims(
        claims,
        str(transaction.get("nonce", "")),
    )
    user = _resolve_google_user(
        db,
        subject=subject,
        email=email,
    )
    raw_session_token, _ = create_session(db, user.id)

    response = RedirectResponse(
        _frontend_redirect(auth="google"),
        status_code=status.HTTP_302_FOUND,
    )
    _set_session_cookie(response, raw_session_token)
    _clear_oauth_cookie(response)
    response.headers["Cache-Control"] = "no-store"
    return response


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
