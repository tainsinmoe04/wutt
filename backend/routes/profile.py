"""Profile routes: get and update user body measurements / style preferences.

Endpoints
    GET  /profile/{user_id}  —  Return profile for a user.
    PUT  /profile/{user_id}  —  Create or update profile fields.

Both endpoints require authentication via ``get_current_user``.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
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

    height_cm: float | None = Field(None, ge=50, le=250, description="Height in centimetres")
    skin_tone: str | None = Field(None, max_length=50)
    style_preference: str | None = Field(None, max_length=100)
    location_city: str | None = Field(None, max_length=100)


class ProfileData(BaseModel):
    """Profile info returned in API responses."""

    id: int
    user_id: int
    height_cm: float | None
    skin_tone: str | None
    style_preference: str | None
    location_city: str | None

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


# ── Routes ─────────────────────────────────────────────


@router.get("/{user_id}")
def get_profile(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuthResponse:
    """Return the profile for *user_id*.

    Raises:
        404 if no profile exists for this user.
    """
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

    Only non-None fields in *body* are applied.  If no profile row exists
    yet, one is created automatically.

    Raises:
        400 if validation fails (handled by Pydantic).
    """
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()

    if profile is None:
        profile = Profile(user_id=user_id)
        db.add(profile)

    # Apply only provided (non-None) fields
    update_data = body.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)

    return {
        "status": "success",
        "data": ProfileData.model_validate(profile).model_dump(),
        "message": "Profile updated successfully.",
    }
