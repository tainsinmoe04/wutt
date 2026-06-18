"""SQLAlchemy ORM models for WUTT database.

Schema:
    users           — id, email, password_hash, created_at
    profiles        — id, user_id (FK), height_cm, skin_tone,
                      style_preference, location_city, updated_at
    wardrobes       — id, user_id (FK), cloudinary_url, cloudinary_public_id,
                      category, subtype, style_tags, material_tags,
                      occasion_tags, color, description, uploaded_at
    style_sessions  — id, user_id (FK), occasion, weather_desc,
                      temperature_c, location, ai_response, created_at
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, ForeignKey,
)
from sqlalchemy.orm import relationship
from database import Base


def _utcnow() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


class User(Base):
    """Registered user account."""

    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    email         = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at    = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Relationships
    profile        = relationship("Profile",        back_populates="user", uselist=False, cascade="all, delete-orphan")
    wardrobes      = relationship("Wardrobe",       back_populates="user", cascade="all, delete-orphan")
    style_sessions = relationship("StyleSession",   back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"


class Profile(Base):
    """User body measurements and style preferences."""

    __tablename__ = "profiles"

    id               = Column(Integer, primary_key=True, index=True)
    user_id          = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    height_cm        = Column(Float,    nullable=True)
    skin_tone        = Column(String(50), nullable=True)
    style_preference = Column(String(100), nullable=True)
    location_city    = Column(String(100), nullable=True)
    updated_at       = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="profile")

    def __repr__(self) -> str:
        return f"<Profile user_id={self.user_id}>"


class Wardrobe(Base):
    """A single clothing item uploaded by the user."""

    __tablename__ = "wardrobes"

    id                  = Column(Integer, primary_key=True, index=True)
    user_id             = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    cloudinary_url      = Column(String(500), nullable=False)
    cloudinary_public_id = Column(String(200), nullable=False)
    category            = Column(String(50),  nullable=True)
    subtype             = Column(String(100), nullable=True)   # e.g. "mini skirt", "blouse", "jeans"
    style_tags          = Column(String(200), nullable=True)   # comma-separated: "casual,summer,street"
    material_tags       = Column(String(200), nullable=True)   # comma-separated: "cotton,denim"
    occasion_tags       = Column(String(200), nullable=True)   # comma-separated: "party,formal"
    color               = Column(String(50),  nullable=True)
    description         = Column(String(255), nullable=True)
    uploaded_at         = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="wardrobes")

    def __repr__(self) -> str:
        return f"<Wardrobe id={self.id} category={self.category!r} subtype={self.subtype!r}>"


class StyleSession(Base):
    """A single outfit-recommendation session."""

    __tablename__ = "style_sessions"

    id            = Column(Integer, primary_key=True, index=True)
    user_id       = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    occasion      = Column(String(100), nullable=True)
    weather_desc  = Column(String(100), nullable=True)
    temperature_c = Column(Float,       nullable=True)
    location      = Column(String(100), nullable=True)
    ai_response   = Column(Text,        nullable=True)
    created_at    = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="style_sessions")

    def __repr__(self) -> str:
        return f"<StyleSession id={self.id} occasion={self.occasion!r}>"
