"""Profile routes: get and update user body measurements / style preferences.

Endpoints
    GET  /profile/{user_id}  —  Return profile for a user.
    PUT  /profile/{user_id}  —  Create or update profile fields.

Both endpoints require authentication via ``get_current_user``.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from database import get_db
from models import User, Profile
from routes.auth import get_current_user

router = APIRouter()

# ── Pydantic Schemas ───────────────────────────────────


class ProfileRequest(BaseModel):
    """Payload for PUT /profile/{user_id}.

    All fields optional — only provided fields are updated.
    """

    model_config = {"extra": "forbid"}

    name: str | None = Field(None, max_length=100)
    gender: str | None = Field(None, max_length=30)
    height_cm: float | None = Field(None, ge=50, le=250, description="Height in centimetres")
    top_size: str | None = Field(None, max_length=20)
    bottom_size: str | None = Field(None, max_length=20)
    shoe_size: str | None = Field(None, max_length=30)
    skin_tone: str | None = Field(None, max_length=50)
    style_preference: str | None = Field(None, max_length=100)
    location_city: str | None = Field(None, max_length=100)
    location_area: str | None = Field(None, max_length=100)
    fit_preference: str | None = Field(None, max_length=50)
    outfit_vibe: str | None = Field(None, max_length=50)
    preferred_colors: str | None = Field(None, max_length=200)
    shopping_style: str | None = Field(None, max_length=50)

    @field_validator(
        "name", "gender", "top_size", "bottom_size", "shoe_size",
        "skin_tone", "style_preference", "location_city", "location_area",
        "fit_preference", "outfit_vibe", "preferred_colors", "shopping_style",
        mode="before",
    )
    @classmethod
    def empty_string_to_none(cls, value: Any) -> Any:
        """Treat blank optional strings as a request to clear the field."""
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class ProfileData(BaseModel):
    """Profile info returned in API responses."""

    id: int
    user_id: int
    name: str | None
    gender: str | None
    height_cm: float | None
    top_size: str | None
    bottom_size: str | None
    shoe_size: str | None
    skin_tone: str | None
    style_preference: str | None
    location_city: str | None
    location_area: str | None
    fit_preference: str | None
    outfit_vibe: str | None
    preferred_colors: str | None
    shopping_style: str | None

    model_config = {"from_attributes": True}


AuthResponse = dict[str, Any]


# ── Helpers ────────────────────────────────────────────


def _get_profile_or_404(user_id: int, db: Session) -> Profile:
    """Return the Profile for *user_id*, or raise 404."""
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    if not profile:
        raise HTTPException(
            status_code=404,
            detail={"status": "error", "data": {}, "message": "Profile not found."},
        )
    return profile


def _require_ownership(user_id: int, current_user: User) -> None:
    """Raise 403 if *current_user* does not own *user_id*."""
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail={
                "status": "error",
                "data": {},
                "message": "You can only access your own profile.",
            },
        )


# ── Routes ─────────────────────────────────────────────


@router.get("/{user_id}")
def get_profile(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuthResponse:
    """Return the profile for *user_id*.

    Raises:
        403 if the current user does not own this profile.
        404 if no profile exists for this user.
    """
    _require_ownership(user_id, current_user)
    profile = _get_profile_or_404(user_id, db)
    return {
        "status": "success",
        "data": ProfileData.model_validate(profile).model_dump(),
        "message": "",
    }


@router.put("/{user_id}")
def update_profile(
    user_id: int,
    body: ProfileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuthResponse:
    """Create or update the profile for *user_id*.

    Only fields present in *body* are applied. Explicit null or blank optional
    strings clear an existing value. If no profile row exists, one is created.

    Raises:
        403 if the current user does not own this profile.
        400 if validation fails (handled by Pydantic).
    """
    _require_ownership(user_id, current_user)
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()

    if profile is None:
        profile = Profile(user_id=user_id)
        db.add(profile)

    # Apply only provided fields. Keep explicit None so optional values clear.
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)

    return {
        "status": "success",
        "data": ProfileData.model_validate(profile).model_dump(),
        "message": "Profile updated successfully.",
    }
