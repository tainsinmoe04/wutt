"""Creation, validation, expiry, and revocation for browser sessions."""

from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from uuid import uuid4

from sqlalchemy.orm import Session

from config import settings
from models import AuthSession


def _utcnow() -> datetime:
    """Return the current timezone-aware UTC time."""
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    """Normalize SQLite's possibly-naive timestamps to timezone-aware UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def hash_session_token(token: str) -> str:
    """Return the SHA-256 digest stored for an opaque session token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(
    db: Session,
    user_id: int,
    *,
    lifetime: timedelta | None = None,
    now: datetime | None = None,
) -> tuple[str, AuthSession]:
    """Create and persist a session, returning its one-time raw token."""
    created_at = now or _utcnow()
    expires_at = created_at + (
        lifetime
        if lifetime is not None
        else timedelta(hours=settings.session_expiry_hours)
    )
    raw_token = secrets.token_urlsafe(32)
    session = AuthSession(
        id=str(uuid4()),
        user_id=user_id,
        token_hash=hash_session_token(raw_token),
        created_at=created_at,
        expires_at=expires_at,
        last_seen_at=created_at,
    )
    try:
        db.add(session)
        db.commit()
        db.refresh(session)
    except Exception:
        db.rollback()
        raise
    return raw_token, session


def lookup_session(
    db: Session,
    raw_token: str,
    *,
    now: datetime | None = None,
) -> AuthSession | None:
    """Return an active session, or None when missing, revoked, or expired."""
    if not raw_token:
        return None
    session = (
        db.query(AuthSession)
        .filter(AuthSession.token_hash == hash_session_token(raw_token))
        .first()
    )
    if session is None or session.revoked_at is not None:
        return None
    if _as_utc(session.expires_at) <= _as_utc(now or _utcnow()):
        return None
    return session


def revoke_session(
    db: Session,
    *,
    session: AuthSession | None = None,
    raw_token: str | None = None,
    now: datetime | None = None,
) -> bool:
    """Revoke one session. Return False when no matching session exists."""
    if session is None and raw_token:
        session = (
            db.query(AuthSession)
            .filter(AuthSession.token_hash == hash_session_token(raw_token))
            .first()
        )
    if session is None:
        return False
    if session.revoked_at is None:
        session.revoked_at = now or _utcnow()
        try:
            db.commit()
            db.refresh(session)
        except Exception:
            db.rollback()
            raise
    return True
