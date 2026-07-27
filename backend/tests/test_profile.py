"""Focused profile persistence and ownership tests."""

import os
import sys

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import Base
from models import Profile, User
from routes.profile import ProfileRequest, get_profile, update_profile


@pytest.fixture()
def db() -> Session:
    """Return an isolated SQLite session using the production ORM metadata."""
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


def make_user(db: Session, email: str) -> User:
    """Create a user without exercising password authentication."""
    user = User(email=email, password_hash="unused-in-profile-tests")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_profile_create_update_and_reload(db: Session) -> None:
    user = make_user(db, "profile-owner@example.com")
    created = update_profile(
        user.id,
        ProfileRequest(
            name="Moe",
            gender="unisex",
            height_cm=170,
            top_size="M",
            bottom_size="L",
            shoe_size="EU 40",
            skin_tone="medium",
            style_preference="minimal, streetwear",
            location_city="Yangon",
            location_area="Bahan",
            fit_preference="regular",
            outfit_vibe="confident",
            preferred_colors="black, navy",
            shopping_style="local-markets",
        ),
        db,
        user,
    )

    assert created["status"] == "success"
    assert created["data"]["name"] == "Moe"
    assert created["data"]["preferred_colors"] == "black, navy"

    # A partial update must not erase omitted fields.
    update_profile(
        user.id,
        ProfileRequest(name="Moe Updated", outfit_vibe="simple"),
        db,
        user,
    )
    db.expire_all()
    reloaded = get_profile(user.id, db, user)["data"]
    assert reloaded["name"] == "Moe Updated"
    assert reloaded["outfit_vibe"] == "simple"
    assert reloaded["location_city"] == "Yangon"
    assert reloaded["top_size"] == "M"


def test_profile_optional_fields_can_be_cleared(db: Session) -> None:
    user = make_user(db, "profile-clear@example.com")
    update_profile(
        user.id,
        ProfileRequest(
            name="Clear Me",
            height_cm=165,
            location_city="Mandalay",
            preferred_colors="black, white",
        ),
        db,
        user,
    )

    # Explicit null and blank strings both mean "clear this optional field".
    cleared = update_profile(
        user.id,
        ProfileRequest(
            name="   ",
            height_cm=None,
            location_city=None,
            preferred_colors="",
        ),
        db,
        user,
    )["data"]
    assert cleared["name"] is None
    assert cleared["height_cm"] is None
    assert cleared["location_city"] is None
    assert cleared["preferred_colors"] is None

    db.expire_all()
    stored = db.query(Profile).filter(Profile.user_id == user.id).one()
    assert stored.name is None
    assert stored.height_cm is None
    assert stored.location_city is None
    assert stored.preferred_colors is None


def test_profile_access_is_limited_to_owner(db: Session) -> None:
    owner = make_user(db, "profile-owner-2@example.com")
    other = make_user(db, "profile-other@example.com")
    update_profile(
        owner.id,
        ProfileRequest(name="Private Profile"),
        db,
        owner,
    )

    with pytest.raises(HTTPException) as read_error:
        get_profile(owner.id, db, other)
    assert read_error.value.status_code == 403

    with pytest.raises(HTTPException) as update_error:
        update_profile(
            owner.id,
            ProfileRequest(name="Unauthorized Change"),
            db,
            other,
        )
    assert update_error.value.status_code == 403

    db.expire_all()
    stored = db.query(Profile).filter(Profile.user_id == owner.id).one()
    assert stored.name == "Private Profile"
