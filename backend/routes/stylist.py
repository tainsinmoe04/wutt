"""Stylist routes: get outfit recommendations and view history.

Endpoints
    POST /stylist/recommend        —  AI-powered outfit recommendation.
    GET  /stylist/history/{user_id} —  List past style sessions.

Requires authentication on both endpoints.
"""

import json
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models import User, Profile, Wardrobe, StyleSession
from routes.auth import get_current_user
from services.weather_svc import get_current_weather, WeatherData
from services.openai_svc import get_outfit_recommendation
from config import settings

logger = logging.getLogger(__name__)

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


# ── Fallback Stylist — Rule-Based Recommendation ────────


# Occasion → preferred categories (most-relevant first)
_OCCASION_CATEGORIES: dict[str, list[str]] = {
    "wedding":   ["traditional", "formal", "dress", "blazer", "jacket", "longyi"],
    "work":      ["formal", "shirt", "blazer", "trousers", "longyi", "smart casual"],
    "party":     ["dress", "jacket", "party", "smart casual", "top", "skirt"],
    "date":      ["smart casual", "dress", "shirt", "top", "skirt", "trousers"],
    "casual":    ["casual", "t-shirt", "shirt", "jeans", "shorts", "trousers"],
    "interview": ["formal", "shirt", "blazer", "trousers", "longyi", "smart casual"],
    "sport":     ["sportswear", "activewear", "t-shirt", "shorts", "athletic"],
    "temple":    ["traditional", "longyi", "formal", "shirt", "shawl"],
}

# Weather → fabric / style hints
_WEATHER_HINTS: dict[str, str] = {
    "hot":     "Choose light, breathable fabrics like cotton or linen.",
    "cool":    "Add a light layer — a jacket, cardigan, or shawl.",
    "rain":    "Pick darker colours that hide splashes. Avoid long hems.",
    "humid":   "Stick to moisture-wicking, non-clingy fabrics.",
    "default": "Dress comfortably for the current weather.",
}

# Skin-tone → colour families
_SKIN_TONE_COLORS: dict[str, list[str]] = {
    "fair":       ["navy", "burgundy", "emerald", "blush", "lavender", "white"],
    "medium":     ["olive", "mustard", "coral", "teal", "cream", "warm brown"],
    "tan":        ["gold", "orange", "deep green", "white", "bright blue", "rust"],
    "dark":       ["jewel tones", "white", "yellow", "fuchsia", "royal blue", "emerald"],
    "olive":      ["warm earth tones", "cream", "peach", "turquoise", "gold", "coral"],
}

# Myanmar-friendly template strings
_FALLBACK_EXPLANATIONS: list[str] = [
    "ဒီ outfit က {occasion} အတွက် အဆင်ပြေပါတယ်။ {color_note} {weather_note}",
    "{occasion} အတွက် ဒီပုံစံက လိုက်ဖက်ပါတယ်။ {color_note} {weather_note}",
    "ဒီနေ့ {occasion} သွားဖို့ ဒီဝတ်စုံက သင့်တော်ပါတယ်။ {color_note} {weather_note}",
]

_WEATHER_TIPS: dict[str, str] = {
    "hot":   "ပူတဲ့ရာသီမို့ ချည်သားပါးပါးလေးတွေ ဝတ်ပါ။ ရေများများသောက်ပါ။",
    "cool":  "အေးနေလို့ အပေါ်ထပ်တစ်ခု ဆောင်းသွားပါ။",
    "rain":  "မိုးရွာနိုင်လို့ ထီးယူဖို့ မမေ့ပါနဲ့။",
    "humid": "စိုစွတ်နေလို့ ချွေးစုပ်တဲ့အထည်တွေ ရွေးပါ။",
}


def _get_weather_hint(weather_desc: str | None, temperature_c: float | None) -> str:
    """Return a short weather hint string based on description and temperature."""
    if not weather_desc and temperature_c is None:
        return _WEATHER_HINTS["default"]
    desc = (weather_desc or "").lower()
    if temperature_c is not None and temperature_c > 32:
        return _WEATHER_HINTS["hot"]
    if "rain" in desc or "drizzle" in desc or "thunderstorm" in desc:
        return _WEATHER_HINTS["rain"]
    if temperature_c is not None and temperature_c < 20:
        return _WEATHER_HINTS["cool"]
    if "humid" in desc or (temperature_c is not None and temperature_c > 28):
        return _WEATHER_HINTS["humid"]
    return _WEATHER_HINTS["default"]


def _get_weather_tip(weather_desc: str | None, temperature_c: float | None) -> str:
    """Return a Myanmar-language weather tip."""
    if not weather_desc and temperature_c is None:
        return "ရာသီဥတုနဲ့လိုက်ဖက်တဲ့အဝတ်ကိုရွေးပါ။"
    desc = (weather_desc or "").lower()
    if temperature_c is not None and temperature_c > 32:
        return _WEATHER_TIPS["hot"]
    if "rain" in desc or "drizzle" in desc or "thunderstorm" in desc:
        return _WEATHER_TIPS["rain"]
    if temperature_c is not None and temperature_c < 20:
        return _WEATHER_TIPS["cool"]
    if "humid" in desc:
        return _WEATHER_TIPS["humid"]
    return "ရာသီဥတုနဲ့လိုက်ဖက်တဲ့အဝတ်ကိုရွေးပါ။"


def _generate_fallback(
    wardrobe_items: list[dict[str, Any]],
    occasion: str,
    weather_desc: str | None = None,
    temperature_c: float | None = None,
    skin_tone: str | None = None,
    style_preference: str | None = None,
) -> dict[str, Any]:
    """Generate a rule-based outfit recommendation from wardrobe metadata.

    Uses occasion → category mapping, weather hints, skin-tone colour
    guidance, and simple colour coordination.  Designed to produce the
    same JSON shape as the AI response so the frontend rendering is
    identical regardless of source.

    Returns:
        Dict with ``outfit`` (list[str]), ``explanation`` (str),
        ``weather_based_tip`` (str).
    """
    import random as _random

    if not wardrobe_items:
        return {
            "outfit": [],
            "explanation": "ဗီရိုထဲမှာ အဝတ်အစားမရှိသေးပါ။",
            "weather_based_tip": "",
        }

    occ_lower = occasion.lower().strip()
    preferred = _OCCASION_CATEGORIES.get(
        occ_lower,
        ["casual", "shirt", "top", "trousers", "t-shirt", "dress"],
    )

    # ── Score each item ──────────────────────────────────
    scored: list[dict[str, Any]] = []
    for item in wardrobe_items:
        cat = (item.get("category") or "").lower().strip()
        color = (item.get("color") or "").lower().strip()
        desc = (item.get("description") or "").lower().strip()

        score = 0

        # Category match: earlier in preferred list = higher score
        try:
            idx = preferred.index(cat)
            score += (len(preferred) - idx) * 10
        except ValueError:
            # Partial match
            for pi, pc in enumerate(preferred):
                if pc in cat or cat in pc:
                    score += (len(preferred) - pi) * 4
                    break

        # Colour / skin-tone bonus
        if skin_tone:
            st_lower = skin_tone.lower().strip()
            for st_key, fav_colors in _SKIN_TONE_COLORS.items():
                if st_key in st_lower or st_lower in st_key:
                    if any(fc in color or color in fc for fc in fav_colors):
                        score += 8
                    break

        # Style preference bonus
        if style_preference:
            sp = style_preference.lower().strip()
            if sp in cat or (sp in desc):
                score += 5

        # Weather bonus — hot weather prefers lighter items
        if temperature_c is not None and temperature_c > 30:
            heavy_keywords = ["wool", "fleece", "leather", "down", "puffer"]
            if not any(kw in cat or kw in desc for kw in heavy_keywords):
                score += 3
        if temperature_c is not None and temperature_c < 18:
            warm_keywords = ["jacket", "sweater", "blazer", "cardigan", "hoodie", "long sleeve"]
            if any(kw in cat or kw in desc for kw in warm_keywords):
                score += 3

        scored.append({"item": item, "score": score, "category": cat, "color": color})

    # ── Pick items (2–5), preferring high-score, category-diverse ──
    scored.sort(key=lambda x: x["score"], reverse=True)

    picked: list[dict[str, Any]] = []
    seen_categories: set[str] = set()

    for s in scored:
        if len(picked) >= 5:
            break
        cat = s["category"]
        # Avoid too many items from the same broad category
        cat_base = cat.split("/")[0].strip()
        if cat_base in seen_categories and len(picked) >= 3:
            continue
        picked.append(s)
        seen_categories.add(cat_base)

    # Ensure at least 2 items
    if len(picked) < 2 and len(scored) >= 2:
        picked = [scored[0]]
        seen = {scored[0]["category"].split("/")[0].strip()}
        for s in scored[1:]:
            if len(picked) >= 5:
                break
            cb = s["category"].split("/")[0].strip()
            if cb not in seen or len(picked) < 2:
                picked.append(s)
                seen.add(cb)

    # ── Build outfit list ────────────────────────────────
    outfit: list[str] = []
    colors_used: list[str] = []
    for p in picked:
        item = p["item"]
        cat = item.get("category") or "item"
        color = item.get("color") or ""
        desc = item.get("description") or ""
        label_parts = [color.capitalize(), cat, desc]
        label = " — ".join(part for part in label_parts if part).strip()
        if not label or label == cat:
            label = f"{color.capitalize()} {cat}".strip() if color else cat.capitalize()
        outfit.append(label)
        if color:
            colors_used.append(color)

    # ── Build explanation ────────────────────────────────
    occasion_my: dict[str, str] = {
        "wedding": "မင်္ဂလာပွဲ", "work": "ရုံးသွား", "party": "ပါတီ",
        "date": "ချိန်းတွေ့", "casual": "အပြင်ထွက်", "interview": "အင်တာဗျူး",
        "sport": "အားကစား", "temple": "ဘုရားဖူး",
    }
    occ_my = occasion_my.get(occ_lower, occasion)

    weather_note = _get_weather_hint(weather_desc, temperature_c)

    if colors_used:
        uniq = list(dict.fromkeys(colors_used))  # preserve order, dedupe
        if len(uniq) == 1:
            color_note = f"{uniq[0]} အရောင်က တစ်သမတ်တည်းဖြစ်ပြီး"
        elif len(uniq) == 2:
            color_note = f"{uniq[0]} နဲ့ {uniq[1]} အရောင်တွဲက လိုက်ဖက်ပြီး"
        else:
            color_note = f"{', '.join(uniq[:-1])} နဲ့ {uniq[-1]} အရောင်တွေက လိုက်ဖက်ပြီး"
    else:
        color_note = "အရောင်တွေက လိုက်ဖက်ပြီး"

    template = _random.choice(_FALLBACK_EXPLANATIONS)
    explanation = template.format(
        occasion=occ_my,
        color_note=color_note,
        weather_note=weather_note,
    )

    weather_tip = _get_weather_tip(weather_desc, temperature_c)

    return {
        "outfit": outfit,
        "explanation": explanation,
        "weather_based_tip": weather_tip,
    }


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

    logger.info(
        "POST /stylist/recommend — user_id=%d occasion=%r key_configured=%s",
        user_id, body.occasion, bool(settings.openai_api_key),
    )

    # ── Fetch context ─────────────────────────────────
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    items = (
        db.query(Wardrobe)
        .filter(Wardrobe.user_id == user_id)
        .all()
    )

    if not items:
        logger.info(
            "POST /stylist/recommend — user_id=%d no wardrobe items → 400",
            user_id,
        )
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "data": {},
                "message": "No wardrobe items found. Please upload some clothes first.",
            },
        )

    logger.info(
        "POST /stylist/recommend — user_id=%d item_count=%d calling OpenAI",
        user_id, len(items),
    )

    # Weather (best-effort with Yangon fallback)
    weather: WeatherData | None = None
    weather_desc = None
    temperature_c = None
    humidity = None
    location = profile.location_city if profile else None
    if location:
        weather = get_current_weather(location)
        if weather:
            weather_desc = weather.description
            temperature_c = weather.temperature_c
            humidity = weather.humidity
            # Use the city that actually resolved (may be fallback)
            location = weather.location

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
    source: str = "ai"
    ai_result: dict[str, Any] | None = None

    try:
        ai_result = get_outfit_recommendation(
            wardrobe_items=wardrobe_images,
            occasion=body.occasion,
            weather_desc=weather_desc,
            temperature_c=temperature_c,
            humidity=humidity,
            height_cm=profile.height_cm if profile else None,
            skin_tone=profile.skin_tone if profile else None,
            style_preference=profile.style_preference if profile else None,
        )
    except Exception as exc:
        # ── Safe server-side logging — never log the API key ──
        cls = type(exc).__qualname__
        mod = type(exc).__module__
        logger.warning(
            "POST /stylist/recommend — user_id=%d AI raised %s.%s → falling back",
            user_id, mod, cls,
        )
        ai_result = None

    if ai_result is None:
        logger.info(
            "POST /stylist/recommend — user_id=%d AI unavailable "
            "(key_configured=%s) → rule-based fallback",
            user_id, bool(settings.openai_api_key),
        )
        ai_result = _generate_fallback(
            wardrobe_items=wardrobe_images,
            occasion=body.occasion,
            weather_desc=weather_desc,
            temperature_c=temperature_c,
            skin_tone=profile.skin_tone if profile else None,
            style_preference=profile.style_preference if profile else None,
        )
        source = "fallback"
    else:
        logger.info(
            "POST /stylist/recommend — user_id=%d outfit_items=%d → 200 (AI)",
            user_id, len(ai_result.get("outfit", [])),
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
            "source": source,
        },
        "message": (
            "Recommendation generated successfully."
            if source == "ai"
            else "Recommendation generated with fallback stylist."
        ),
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
