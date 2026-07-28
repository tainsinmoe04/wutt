"""Focused tests for Phase 2.1 authentication infrastructure."""

from collections.abc import Generator
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, Response
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from config import settings
from database import Base
from models import AuthIdentity, AuthSession, User
from routes.auth import (
    LoginRequest,
    RegisterRequest,
    _create_jwt,
    get_current_user,
    login,
    logout,
    register,
)
from services.auth_session_svc import (
    create_session,
    hash_session_token,
    lookup_session,
    revoke_session,
)


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    """Return an isolated SQLite session using the production metadata."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def make_user(db: Session, email: str = "auth@example.com") -> User:
    """Persist a minimal user fixture."""
    user = User(email=email, password_hash="$2b$12$unused")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_request(*, authorization: str = "", cookies: dict[str, str] | None = None) -> Request:
    """Build a Starlette request containing only authentication metadata."""
    headers: list[tuple[bytes, bytes]] = []
    if authorization:
        headers.append((b"authorization", authorization.encode("latin-1")))
    if cookies:
        cookie_value = "; ".join(f"{key}={value}" for key, value in cookies.items())
        headers.append((b"cookie", cookie_value.encode("latin-1")))
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/auth/me",
        "headers": headers,
        "query_string": b"",
        "server": ("testserver", 80),
        "client": ("testclient", 123),
        "scheme": "http",
    })


def test_auth_models_and_identity_uniqueness(db: Session) -> None:
    user = make_user(db)
    db.add(AuthIdentity(
        user_id=user.id,
        provider="google",
        provider_subject="subject-123",
        provider_email=user.email,
        email_verified=True,
    ))
    db.commit()

    db.add(AuthIdentity(
        user_id=user.id,
        provider="google",
        provider_subject="subject-123",
        provider_email="other@example.com",
        email_verified=True,
    ))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_session_creation_stores_only_hash_and_can_be_looked_up(db: Session) -> None:
    user = make_user(db)
    raw_token, session = create_session(db, user.id)

    assert raw_token
    assert session.token_hash == hash_session_token(raw_token)
    assert raw_token != session.token_hash
    assert db.query(AuthSession).filter_by(token_hash=raw_token).first() is None
    assert lookup_session(db, raw_token).id == session.id


def test_expired_and_revoked_sessions_are_rejected(db: Session) -> None:
    user = make_user(db)
    now = datetime.now(timezone.utc)

    expired_token, _ = create_session(
        db,
        user.id,
        lifetime=timedelta(seconds=1),
        now=now - timedelta(minutes=1),
    )
    assert lookup_session(db, expired_token, now=now) is None

    active_token, active_session = create_session(db, user.id, now=now)
    assert revoke_session(db, raw_token=active_token, now=now) is True
    assert active_session.revoked_at is not None
    assert lookup_session(db, active_token, now=now) is None
    assert revoke_session(db, raw_token="missing") is False


def test_get_current_user_accepts_browser_session(db: Session) -> None:
    user = make_user(db)
    raw_token, _ = create_session(db, user.id)

    request = make_request(cookies={settings.session_cookie_name: raw_token})
    assert get_current_user(request, db).id == user.id


def test_invalid_browser_session_fails_closed_without_jwt_fallback(db: Session) -> None:
    user = make_user(db)
    legacy_jwt = _create_jwt(user.id, user.email)
    request = make_request(cookies={
        settings.session_cookie_name: "invalid-session",
        "wutt_token": legacy_jwt,
    })

    with pytest.raises(HTTPException) as error:
        get_current_user(request, db)
    assert error.value.status_code == 401
    assert "session" in error.value.detail["message"].lower()


def test_legacy_bearer_and_cookie_jwts_remain_compatible(db: Session) -> None:
    user = make_user(db)
    token = _create_jwt(user.id, user.email)

    bearer_request = make_request(authorization=f"Bearer {token}")
    assert get_current_user(bearer_request, db).id == user.id

    cookie_request = make_request(cookies={"wutt_token": token})
    assert get_current_user(cookie_request, db).id == user.id


def test_existing_register_and_login_endpoints_still_issue_jwt(
    db: Session,
) -> None:
    register_response = Response()
    registered = register(
        RegisterRequest(email="existing-flow@example.com", password="password1"),
        register_response,
        db,
    )
    assert registered["data"]["token"]
    assert "wutt_token=" in register_response.headers["set-cookie"]

    login_response = Response()
    logged_in = login(
        LoginRequest(email="existing-flow@example.com", password="password1"),
        login_response,
        db,
    )
    assert logged_in["data"]["token"]
    assert "wutt_token=" in login_response.headers["set-cookie"]


def test_login_rejects_unknown_email_and_incorrect_password(db: Session) -> None:
    register(
        RegisterRequest(email="real-user@example.com", password="password1"),
        Response(),
        db,
    )

    for email, password in (
        ("missing-user@example.com", "password1"),
        ("real-user@example.com", "incorrect1"),
    ):
        with pytest.raises(HTTPException) as error:
            login(LoginRequest(email=email, password=password), Response(), db)
        assert error.value.status_code == 401
        assert error.value.detail["message"] == "Invalid email or password."


def test_disabled_demo_login_rejects_configured_credentials(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "demo_login_enabled", False)
    monkeypatch.setattr(settings, "demo_login_email", "demo@example.com")
    monkeypatch.setattr(settings, "demo_login_password", "demo-password1")

    with pytest.raises(HTTPException) as error:
        login(
            LoginRequest(
                email="demo@example.com",
                password="demo-password1",
            ),
            Response(),
            db,
        )

    assert error.value.status_code == 401
    assert db.query(User).count() == 0


def test_enabled_demo_login_creates_only_the_configured_account(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "demo_login_enabled", True)
    monkeypatch.setattr(settings, "demo_login_email", "demo@example.com")
    monkeypatch.setattr(settings, "demo_login_password", "demo-password1")

    response = Response()
    result = login(
        LoginRequest(email="DEMO@example.com", password="demo-password1"),
        response,
        db,
    )

    demo_user = db.query(User).one()
    assert result["data"]["email"] == "demo@example.com"
    assert result["data"]["token"]
    assert demo_user.email == "demo@example.com"
    assert demo_user.password_hash != "demo-password1"
    assert "wutt_token=" in response.headers["set-cookie"]

    for email, password in (
        ("other@example.com", "demo-password1"),
        ("demo@example.com", "wrong-password1"),
    ):
        with pytest.raises(HTTPException) as error:
            login(LoginRequest(email=email, password=password), Response(), db)
        assert error.value.status_code == 401


def test_disabling_demo_mode_blocks_the_persisted_demo_account(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "demo_login_enabled", True)
    monkeypatch.setattr(settings, "demo_login_email", "demo@example.com")
    monkeypatch.setattr(settings, "demo_login_password", "demo-password1")
    login(
        LoginRequest(email="demo@example.com", password="demo-password1"),
        Response(),
        db,
    )

    monkeypatch.setattr(settings, "demo_login_enabled", False)
    with pytest.raises(HTTPException) as error:
        login(
            LoginRequest(email="demo@example.com", password="demo-password1"),
            Response(),
            db,
        )

    assert error.value.status_code == 401


def test_demo_login_never_takes_over_existing_account(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    register(
        RegisterRequest(email="demo@example.com", password="original1"),
        Response(),
        db,
    )
    monkeypatch.setattr(settings, "demo_login_enabled", True)
    monkeypatch.setattr(settings, "demo_login_email", "demo@example.com")
    monkeypatch.setattr(settings, "demo_login_password", "demo-password1")

    with pytest.raises(HTTPException) as error:
        login(
            LoginRequest(email="demo@example.com", password="demo-password1"),
            Response(),
            db,
        )

    assert error.value.status_code == 401
    assert login(
        LoginRequest(email="demo@example.com", password="original1"),
        Response(),
        db,
    )["status"] == "success"


def test_demo_email_is_reserved_while_demo_mode_is_enabled(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "demo_login_enabled", True)
    monkeypatch.setattr(settings, "demo_login_email", "demo@example.com")

    with pytest.raises(HTTPException) as error:
        register(
            RegisterRequest(email="demo@example.com", password="password1"),
            Response(),
            db,
        )

    assert error.value.status_code == 409
    assert db.query(User).count() == 0


def test_logout_revokes_session_and_expires_auth_cookies(db: Session) -> None:
    user = make_user(db)
    raw_token, auth_session = create_session(db, user.id)
    request = make_request(cookies={
        settings.session_cookie_name: raw_token,
        "wutt_token": _create_jwt(user.id, user.email),
    })
    response = Response()

    result = logout(request, response, db)

    db.refresh(auth_session)
    set_cookie_headers = response.headers.getlist("set-cookie")
    assert result["status"] == "success"
    assert auth_session.revoked_at is not None
    assert any(
        header.startswith(f"{settings.session_cookie_name}=")
        and "Max-Age=0" in header
        for header in set_cookie_headers
    )
    assert any(
        header.startswith("wutt_token=") and "Max-Age=0" in header
        for header in set_cookie_headers
    )


def test_logout_without_active_session_is_idempotent(db: Session) -> None:
    response = Response()

    result = logout(make_request(), response, db)

    assert result["status"] == "success"
    assert len(response.headers.getlist("set-cookie")) == 2
