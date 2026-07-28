"""Focused tests for manual wardrobe upload and metadata editing."""

import asyncio
from collections.abc import Generator
from io import BytesIO

from fastapi import UploadFile
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from starlette.datastructures import Headers

from database import Base
from models import User, Wardrobe
from routes import wardrobe


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    """Return an isolated database containing the production models."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def user(db: Session) -> User:
    """Create the authenticated wardrobe owner."""
    value = User(email="wardrobe@example.com", password_hash="unused")
    db.add(value)
    db.commit()
    db.refresh(value)
    return value


def image_upload() -> UploadFile:
    """Return a small valid image-like upload for route-level tests."""
    return UploadFile(
        filename="shirt.jpg",
        file=BytesIO(b"manual-wardrobe-image"),
        headers=Headers({"content-type": "image/jpeg"}),
    )


def test_upload_saves_manual_metadata_without_ai_analysis(
    db: Session,
    user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upload_calls: list[tuple[bytes, str]] = []

    def fake_upload(raw: bytes, public_id: str) -> tuple[str, str]:
        upload_calls.append((raw, public_id))
        return "https://images.example/manual-shirt.jpg", public_id

    monkeypatch.setattr(wardrobe, "upload_image", fake_upload)

    result = asyncio.run(wardrobe.upload_wardrobe_item(
        file=image_upload(),
        category="Top",
        subtype="Linen shirt",
        style_tags="minimal, casual",
        material_tags=None,
        occasion_tags="work, weekend",
        brand=None,
        formality_level=None,
        season_suitability=None,
        color="Navy",
        description="Relaxed fit",
        db=db,
        current_user=user,
    ))

    stored = db.query(Wardrobe).one()
    assert len(upload_calls) == 1
    assert result["status"] == "success"
    assert result["data"]["cloudinary_url"] == "https://images.example/manual-shirt.jpg"
    reloaded = wardrobe.list_wardrobe(user.id, db, user)
    assert reloaded["data"][0]["cloudinary_url"] == (
        "https://images.example/manual-shirt.jpg"
    )
    assert reloaded["data"][0]["cloudinary_public_id"] == stored.cloudinary_public_id
    assert stored.category == "Top"
    assert stored.subtype == "Linen shirt"
    assert stored.color == "Navy"
    assert stored.description == "Relaxed fit"
    assert stored.style_tags == "minimal, casual"
    assert stored.occasion_tags == "work, weekend"


def test_upload_without_ai_metadata_still_creates_wardrobe_item(
    db: Session,
    user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        wardrobe,
        "upload_image",
        lambda raw, public_id: ("https://images.example/item.jpg", public_id),
    )

    result = asyncio.run(wardrobe.upload_wardrobe_item(
        file=image_upload(),
        category=None,
        subtype=None,
        style_tags=None,
        material_tags=None,
        occasion_tags=None,
        brand=None,
        formality_level=None,
        season_suitability=None,
        color=None,
        description=None,
        db=db,
        current_user=user,
    ))

    assert result["status"] == "success"
    assert db.query(Wardrobe).count() == 1


def test_manual_metadata_can_be_edited_without_changing_image(
    db: Session,
    user: User,
) -> None:
    item = Wardrobe(
        user_id=user.id,
        cloudinary_url="https://images.example/original.jpg",
        cloudinary_public_id="original-id",
        category="Top",
        subtype="Shirt",
        color="Blue",
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    result = wardrobe.update_wardrobe_item(
        item.id,
        wardrobe.WardrobeItemUpdate(
            category="Outerwear",
            subtype="Overshirt",
            color=" Navy ",
            description="Lightweight layer",
            style_tags="casual, utility",
            occasion_tags="weekend, travel",
            material_tags="cotton",
            brand="Local atelier",
            formality_level="Smart casual",
            season_suitability="Hot season",
        ),
        db,
        user,
    )

    db.refresh(item)
    assert result["status"] == "success"
    assert item.category == "Outerwear"
    assert item.subtype == "Overshirt"
    assert item.color == "Navy"
    assert item.description == "Lightweight layer"
    assert item.style_tags == "casual, utility"
    assert item.occasion_tags == "weekend, travel"
    assert item.material_tags == "cotton"
    assert item.brand == "Local atelier"
    assert item.formality_level == "Smart casual"
    assert item.season_suitability == "Hot season"
    assert item.cloudinary_url == "https://images.example/original.jpg"
    assert item.cloudinary_public_id == "original-id"
