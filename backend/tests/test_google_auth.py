"""Focused mocked tests for the Phase 2.2 Google OAuth backend."""

import asyncio
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlsplit

from fastapi import HTTPException, Request
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from config import settings
from database import Base
from models import AuthIdentity, AuthSession, User
from routes import auth


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    """Return an isolated database session."""
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


@pytest.fixture(autouse=True)
def google_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure safe Google settings for direct route tests."""
    monkeypatch.setattr(settings, "debug", True)
    monkeypatch.setattr(settings, "jwt_secret_key", "phase-22-test-secret")
    monkeypatch.setattr(settings, "google_client_id", "google-client-id")
    monkeypatch.setattr(settings, "google_client_secret", "google-client-secret")
    monkeypatch.setattr(
        settings,
        "google_redirect_uri",
        "http://testserver/auth/google/callback",
    )
    monkeypatch.setattr(settings, "frontend_url", "http://localhost:5500")


def _cookie_from_response(response, name: str) -> str | None:
    """Extract one cookie value from a response's Set-Cookie headers."""
    cookies = SimpleCookie()
    for header in response.headers.getlist("set-cookie"):
        cookies.load(header)
    morsel = cookies.get(name)
    return morsel.value if morsel else None


def _request_with_cookie(name: str, value: str) -> Request:
    """Build a callback request carrying the signed OAuth cookie."""
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/auth/google/callback",
        "headers": [(b"cookie", f"{name}={value}".encode("latin-1"))],
        "query_string": b"",
        "server": ("testserver", 80),
        "client": ("testclient", 123),
        "scheme": "http",
    })


def _start_transaction() -> tuple[str, str, dict]:
    """Start OAuth and return public state, cookie, and transaction."""
    response = auth.google_start()
    query = parse_qs(urlsplit(response.headers["location"]).query)
    cookie = _cookie_from_response(response, auth.OAUTH_STATE_COOKIE)
    assert cookie
    return query["state"][0], cookie, auth._decode_oauth_transaction(cookie)


def _valid_claims(transaction: dict, **overrides: object) -> dict:
    claims = {
        "iss": "https://accounts.google.com",
        "aud": "google-client-id",
        "sub": "google-subject-1",
        "email": "person@example.com",
        "email_verified": True,
        "nonce": transaction["nonce"],
        "exp": (datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp(),
    }
    claims.update(overrides)
    return claims


def _complete_login(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    *,
    claims: dict,
    state: str,
    cookie: str,
    transaction: dict,
):
    """Complete OAuth with a mocked token exchange and ID-token verifier."""
    async def exchange(code: str, verifier: str) -> dict[str, str]:
        assert code == "authorization-code"
        assert verifier == transaction["verifier"]
        return {"id_token": "mock-google-id-token", "access_token": "never-exposed"}

    monkeypatch.setattr(auth, "_exchange_google_code", exchange)
    monkeypatch.setattr(auth, "_verify_google_token", lambda encoded: claims)
    return asyncio.run(auth.google_callback(
        request=_request_with_cookie(auth.OAUTH_STATE_COOKIE, cookie),
        db=db,
        code="authorization-code",
        state=state,
        error=None,
    ))


def test_google_start_has_state_nonce_and_pkce() -> None:
    response = auth.google_start()
    query = parse_qs(urlsplit(response.headers["location"]).query)

    assert response.status_code == 302
    assert query["response_type"] == ["code"]
    assert query["scope"] == ["openid email profile"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["state"][0]
    assert query["nonce"][0]
    assert query["code_challenge"][0]
    assert "no-store" in response.headers["cache-control"]
    assert _cookie_from_response(response, auth.OAUTH_STATE_COOKIE)


def test_google_start_returns_to_frontend_when_configuration_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "google_client_secret", "")

    response = auth.google_start()
    query = parse_qs(urlsplit(response.headers["location"]).query)

    assert response.status_code == 302
    assert response.headers["location"].startswith("http://localhost:5500")
    assert query == {
        "auth_error": ["google"],
        "auth_reason": ["configuration"],
    }
    assert "no-store" in response.headers["cache-control"]
    assert _cookie_from_response(response, auth.OAUTH_STATE_COOKIE) is None


def test_first_google_login_creates_identity_user_and_session_without_jwt(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, cookie, transaction = _start_transaction()
    response = _complete_login(
        db,
        monkeypatch,
        claims=_valid_claims(transaction),
        state=state,
        cookie=cookie,
        transaction=transaction,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "http://localhost:5500?auth=google"
    assert "mock-google-id-token" not in response.headers["location"]
    assert "never-exposed" not in response.headers["location"]
    assert _cookie_from_response(response, settings.session_cookie_name)
    assert _cookie_from_response(response, "wutt_token") is None

    user = db.query(User).filter(User.email == "person@example.com").one()
    assert user.password_hash is None
    identity = db.query(AuthIdentity).one()
    assert identity.user_id == user.id
    assert identity.provider_subject == "google-subject-1"
    assert db.query(AuthSession).filter(AuthSession.user_id == user.id).count() == 1

    session_cookie = _cookie_from_response(response, settings.session_cookie_name)
    restored = auth.get_current_user(
        _request_with_cookie(settings.session_cookie_name, session_cookie),
        db,
    )
    assert restored.id == user.id


def test_returning_google_login_reuses_identity_and_creates_new_session(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for _ in range(2):
        state, cookie, transaction = _start_transaction()
        _complete_login(
            db,
            monkeypatch,
            claims=_valid_claims(transaction),
            state=state,
            cookie=cookie,
            transaction=transaction,
        )

    assert db.query(User).count() == 1
    assert db.query(AuthIdentity).count() == 1
    assert db.query(AuthSession).count() == 2


def test_verified_google_email_links_existing_password_user(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = User(email="person@example.com", password_hash="existing-hash")
    db.add(existing)
    db.commit()
    db.refresh(existing)

    state, cookie, transaction = _start_transaction()
    _complete_login(
        db,
        monkeypatch,
        claims=_valid_claims(transaction),
        state=state,
        cookie=cookie,
        transaction=transaction,
    )
    assert db.query(User).count() == 1
    assert db.query(AuthIdentity).one().user_id == existing.id


def test_conflicting_google_subject_for_linked_user_is_rejected(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = User(email="person@example.com", password_hash=None)
    db.add(user)
    db.flush()
    db.add(AuthIdentity(
        user_id=user.id,
        provider="google",
        provider_subject="already-linked-subject",
        provider_email=user.email,
        email_verified=True,
    ))
    db.commit()

    state, cookie, transaction = _start_transaction()
    with pytest.raises(HTTPException) as error:
        _complete_login(
            db,
            monkeypatch,
            claims=_valid_claims(transaction, sub="different-subject"),
            state=state,
            cookie=cookie,
            transaction=transaction,
        )
    assert error.value.status_code == 409
    assert db.query(AuthSession).count() == 0


def test_database_rejects_two_google_identities_for_one_user(
    db: Session,
) -> None:
    user = User(email="person@example.com", password_hash=None)
    db.add(user)
    db.flush()
    db.add(AuthIdentity(
        user_id=user.id,
        provider="google",
        provider_subject="subject-one",
        provider_email=user.email,
        email_verified=True,
    ))
    db.commit()
    db.add(AuthIdentity(
        user_id=user.id,
        provider="google",
        provider_subject="subject-two",
        provider_email=user.email,
        email_verified=True,
    ))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


@pytest.mark.parametrize(
    "overrides,expected_status",
    [
        ({"iss": "https://attacker.example"}, 401),
        ({"aud": "other-client"}, 401),
        ({"email_verified": False}, 403),
        ({"nonce": "wrong-nonce"}, 401),
        ({"exp": 1}, 401),
    ],
)
def test_callback_rejects_invalid_required_claims(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict,
    expected_status: int,
) -> None:
    state, cookie, transaction = _start_transaction()
    with pytest.raises(HTTPException) as error:
        _complete_login(
            db,
            monkeypatch,
            claims=_valid_claims(transaction, **overrides),
            state=state,
            cookie=cookie,
            transaction=transaction,
        )
    assert error.value.status_code == expected_status
    assert db.query(AuthSession).count() == 0


def test_callback_rejects_state_mismatch_before_token_exchange(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, cookie, _ = _start_transaction()

    async def must_not_exchange(code: str, verifier: str) -> dict:
        raise AssertionError("token exchange must not run")

    monkeypatch.setattr(auth, "_exchange_google_code", must_not_exchange)
    with pytest.raises(HTTPException) as error:
        asyncio.run(auth.google_callback(
            request=_request_with_cookie(auth.OAUTH_STATE_COOKIE, cookie),
            db=db,
            code="authorization-code",
            state="wrong-state",
            error=None,
        ))
    assert error.value.status_code == 400


def test_google_start_returns_503_when_no_frontend_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "google_client_secret", "")
    monkeypatch.setattr(settings, "frontend_url", "")
    with pytest.raises(HTTPException) as error:
        auth.google_start()
    assert error.value.status_code == 503
