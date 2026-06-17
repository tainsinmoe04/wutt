"""Stylist routes: get outfit recommendations and view history.

Endpoints
    POST /stylist/recommend        —  AI-powered outfit recommendation.
    GET  /stylist/history/{user_id} —  List past style sessions.

Requires authentication on both endpoints.
"""

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models import User, Profile, Wardrobe, StyleSession
from routes.auth import get_current_user
from services.weather_svc import get_current_weather
from services.openai_svc import get_outfit_recommendation

router = APIRouter()


# ── Pydantic Schemas ───────────────────────────────────


class RecommendRequest(BaseModel):
    """Payload for POST /stylist/recommend."""

    occasion: str = Field(
        ..., min_length=1, max_length=100,
        description="e.g. wedding, work, party, dinner date",
    )


class OutfitData(BaseModel):
    """Structured outfit recommendation returned in API responses."""

    outfit: list[str] = Field(default_factory=list, description="2–5 items to wear, ordered")
    explanation: str = Field(default="", description="Why this outfit works, Myanmar-friendly")
    weather_based_tip: str = Field(default="", description="One practical weather tip")


class RecommendResponse(BaseModel):
    """Full recommendation response including context."""

    id: int
    occasion: str | None
    weather_desc: str | None
    temperature_c: float | None
    location: str | None
    outfit: list[str]
    explanation: str
    weather_based_tip: str
    created_at: str


class StyleSessionData(BaseModel):
    """Style session returned in history API responses."""

    id: int
    occasion: str | None
    weather_desc: str | None
    temperature_c: float | None
    location: str | None
    ai_response: str | None
    created_at: datetime | None  # Serialized to ISO-8601 via model_dump(mode='json')

    model_config = {"from_attributes": True}


AuthResponse = dict[str, Any]


# ── Helpers ────────────────────────────────────────────


def _isoformat(dt) -> str:
    """Return *dt* as ISO-8601 string or empty string."""
    if dt is None:
        return ""
    return dt.isoformat()


def _extract_outfit_fields(ai_result: dict[str, Any]) -> tuple[list[str], str, str]:
    """Safely extract outfit, explanation, and weather_based_tip from AI result."""
    if not ai_result:
        return [], "", ""
    return (
        ai_result.get("outfit") or [],
        ai_result.get("explanation") or "",
        ai_result.get("weather_based_tip") or "",
    )


# ── Routes ─────────────────────────────────────────────


@router.post("/recommend")
def recommend_outfit(
    body: RecommendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuthResponse:
    """Generate an AI outfit recommendation.

    Fetches the user's profile + wardrobe, current weather (by profile city),
    then asks GPT-4o Vision to pick the best outfit for the occasion.

    Returns a structured recommendation with outfit items, explanation,
    and a weather-based tip.
    """
    user_id = current_user.id

    # ── Fetch context ─────────────────────────────────
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    items = (
        db.query(Wardrobe)
        .filter(Wardrobe.user_id == user_id)
        .all()
    )

    if not items:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "data": {},
                "message": "No wardrobe items found. Please upload some clothes first.",
            },
        )

    # Weather (best-effort)
    weather_desc = None
    temperature_c = None
    location = profile.location_city if profile else None
    if location:
        weather = get_current_weather(location)
        if weather:
            weather_desc = weather["description"]
            temperature_c = weather["temperature_c"]

    # ── Prepare image list for OpenAI ──────────────────
    wardrobe_images: list[dict[str, Any]] = []
    for item in items:
        wardrobe_images.append({
            "url": item.cloudinary_url,
            "category": item.category,
            "color": item.color,
            "description": item.description,
        })

    # ── Call AI ────────────────────────────────────────
    ai_result = get_outfit_recommendation(
        wardrobe_items=wardrobe_images,
        occasion=body.occasion,
        weather_desc=weather_desc,
        temperature_c=temperature_c,
        height_cm=profile.height_cm if profile else None,
        skin_tone=profile.skin_tone if profile else None,
        style_preference=profile.style_preference if profile else None,
    )

    if ai_result is None:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "error",
                "data": {},
                "message": "AI recommendation is unavailable right now. Please try again later.",
            },
        )

    outfit, explanation, weather_based_tip = _extract_outfit_fields(ai_result)

    # ── Save session ───────────────────────────────────
    session = StyleSession(
        user_id=user_id,
        occasion=body.occasion,
        weather_desc=weather_desc,
        temperature_c=temperature_c,
        location=location,
        ai_response=json.dumps(ai_result, ensure_ascii=False),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return {
        "status": "success",
        "data": {
            "id": session.id,
            "occasion": session.occasion,
            "weather_desc": session.weather_desc,
            "temperature_c": session.temperature_c,
            "location": session.location,
            "outfit": outfit,
            "explanation": explanation,
            "weather_based_tip": weather_based_tip,
            "created_at": _isoformat(session.created_at),
        },
        "message": "Recommendation generated successfully.",
    }


@router.get("/history/{user_id}")
def get_history(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuthResponse:
    """Return all past style sessions for *user_id*, newest first.

    Raises:
        403 if the current user does not own this history.
    """
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail={
                "status": "error",
                "data": {},
                "message": "You can only access your own style history.",
            },
        )
    sessions = (
        db.query(StyleSession)
        .filter(StyleSession.user_id == user_id)
        .order_by(StyleSession.created_at.desc())
        .all()
    )

    data = []
    for s in sessions:
        data.append(StyleSessionData.model_validate(s).model_dump(mode="json"))

    return {"status": "success", "data": data, "message": ""}
