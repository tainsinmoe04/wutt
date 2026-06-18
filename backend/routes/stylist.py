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
#
#  Design principles
#  • Valid outfits only — never dress+dress, top+top, or dress+top+bottom.
#  • Occasion-aware — interview/wedding/casual each have distinct rules.
#  • Honest suitability — if nothing fits, say so clearly.
#  • Natural Myanmar language — no awkward mixed English.


# ── Category classification maps ─────────────────────────

# Keywords that identify an item as a one-piece (dress / gown / jumpsuit).
_DRESS_KEYWORDS: tuple[str, ...] = (
    "dress", "gown", "jumpsuit", "one-piece", "one piece", "onepiece",
    "ဂါဝန်", "တစ်ဆက်တည်းဝတ်စုံ",
)

# Keywords that identify a top (shirt, blouse, t-shirt, blazer worn on top).
_TOP_KEYWORDS: tuple[str, ...] = (
    "top", "shirt", "blouse", "t-shirt", "tshirt", "sweater",
    "hoodie", "blazer", "jacket", "အပေါ်ဝတ်", "အင်္ကျီ",
)

# Keywords that identify a bottom (trousers, pants, jeans, shorts, skirt).
_BOTTOM_KEYWORDS: tuple[str, ...] = (
    "bottom", "trouser", "pant", "jeans", "short", "skirt",
    "ဘောင်းဘီ", "အောက်ဝတ်", "လုံချည်",
)

# Keywords that identify traditional/Myanmar/longyi items.
_TRADITIONAL_KEYWORDS: tuple[str, ...] = (
    "traditional", "myanmar", "longyi", "မြန်မာ", "ရိုးရာ",
    "လုံချည်", "ထဘီ",
)

# Keywords that identify outerwear / layering items.
_OUTERWEAR_KEYWORDS: tuple[str, ...] = (
    "outerwear", "coat", "cardigan", "shawl", "jacket",
    "အင်္ကျီအပေါ်ခံ",
)

# Keywords that identify accessories.
_ACCESSORY_KEYWORDS: tuple[str, ...] = (
    "accessory", "bag", "belt", "jewelry", "scarf", "hat",
    "အသုံးအဆောင်",
)

# Keywords that identify shoes.
_SHOES_KEYWORDS: tuple[str, ...] = (
    "shoes", "sandal", "heel", "ဖိနပ်",
)


# ── Occasion-specific colours ────────────────────────────

_PARTY_COLORS: set[str] = {
    "red", "black", "gold", "silver", "purple", "pink", "white",
    "အနီ", "အနက်", "ခရမ်း", "ပန်းရောင်", "အဖြူ",
}

_INTERVIEW_COLORS: set[str] = {
    "navy", "white", "beige", "black", "gray", "grey", "နေပယ်ပြာ",
    "အဖြူ", "ဘဲဂျီ", "အနက်", "မီးခိုး",
}

_WEDDING_COLORS: set[str] = {
    "red", "gold", "pink", "purple", "navy", "green", "cream",
    "အနီ", "ပန်းရောင်", "ခရမ်း", "နေပယ်ပြာ", "အစိမ်း",
}

_BRIGHT_ACCENT_COLORS: set[str] = {
    "yellow", "orange", "neon", "အဝါ",
}


# ── Weather tips in natural Myanmar ──────────────────────

_WEATHER_TIPS: dict[str, str] = {
    "hot": (
        "ရာသီဥတုပူလို့ ပေါ့ပါးပြီး လေဝင်လေထွက်ကောင်းတဲ့အဝတ်ကို ရွေးပါ။"
        " ရေများများသောက်ပါ။"
    ),
    "cool": (
        "အေးနေလို့ အပေါ်ထပ်တစ်ခု ထပ်ဆောင်းသွားပါ။"
    ),
    "rain": (
        "မိုးရွာနိုင်လို့ ထီးယူဖို့ မမေ့ပါနဲ့။"
    ),
    "humid": (
        "စိုစွတ်နေလို့ ချွေးစုပ်တဲ့အထည်တွေ ရွေးပါ။"
    ),
}


# ── Helpers ──────────────────────────────────────────────


def _classify_item(item: dict[str, Any]) -> str:
    """Classify a wardrobe item into a broad type.

    Returns one of: ``dress``, ``top``, ``bottom``, ``traditional``,
    ``outerwear``, ``accessory``, ``shoes``, ``unknown``.
    """
    cat = (item.get("category") or "").lower().strip()
    desc = (item.get("description") or "").lower().strip()
    combined = f"{cat} {desc}"

    # Order matters — check dress before top (blazer/jacket can be ambiguous)
    if any(kw in cat for kw in _DRESS_KEYWORDS):
        return "dress"
    if any(kw in cat for kw in _TRADITIONAL_KEYWORDS):
        return "traditional"
    if any(kw in cat for kw in _OUTERWEAR_KEYWORDS):
        return "outerwear"
    if any(kw in cat for kw in _TOP_KEYWORDS):
        return "top"
    if any(kw in cat for kw in _BOTTOM_KEYWORDS):
        return "bottom"
    if any(kw in cat for kw in _ACCESSORY_KEYWORDS):
        return "accessory"
    if any(kw in cat for kw in _SHOES_KEYWORDS):
        return "shoes"

    # Fallback: try description
    if any(kw in combined for kw in _DRESS_KEYWORDS):
        return "dress"
    if any(kw in combined for kw in _TOP_KEYWORDS):
        return "top"
    if any(kw in combined for kw in _BOTTOM_KEYWORDS):
        return "bottom"

    return "unknown"


def _color_matches(color: str, allowed: set[str]) -> bool:
    """Check whether *color* belongs to *allowed* set (case-insensitive)."""
    if not color:
        return False
    return color.lower().strip() in allowed


def _item_label(item: dict[str, Any]) -> str:
    """Build a human-readable Myanmar label for a wardrobe item."""
    cat = item.get("category") or ""
    color = item.get("color") or ""
    desc = item.get("description") or ""

    # Map common category names to Myanmar
    cat_my_map: dict[str, str] = {
        "top": "အပေါ်ဝတ်", "bottom": "အောက်ဝတ်", "dress": "ဂါဝန်",
        "outerwear": "အပေါ်ထပ်", "accessory": "အသုံးအဆောင်", "shoes": "ဖိနပ်",
        "traditional": "မြန်မာဝတ်စုံ", "longyi": "လုံချည်",
        "shirt": "အပေါ်ဝတ်", "blouse": "အပေါ်ဝတ်", "t-shirt": "အပေါ်ဝတ်",
        "sweater": "အပေါ်ဝတ်", "hoodie": "အပေါ်ဝတ်", "blazer": "အပေါ်ဝတ်",
        "jacket": "အပေါ်ဝတ်",
        "trousers": "အောက်ဝတ်", "pants": "အောက်ဝတ်", "jeans": "အောက်ဝတ်",
        "shorts": "အောက်ဝတ်", "skirt": "အောက်ဝတ်",
        "gown": "ဂါဝန်", "jumpsuit": "တစ်ဆက်တည်းဝတ်စုံ",
        "coat": "အပေါ်ထပ်", "cardigan": "အပေါ်ထပ်",
    }
    cat_my = cat_my_map.get(cat.lower().strip() if cat else "", cat)

    if color and desc:
        return f"{color} {cat_my} — {desc}"
    if color:
        return f"{color} {cat_my}"
    if desc:
        return f"{cat_my} — {desc}"
    return cat_my


def _get_weather_tip(
    weather_desc: str | None,
    temperature_c: float | None,
) -> str:
    """Return a natural Myanmar weather tip."""
    if not weather_desc and temperature_c is None:
        return (
            "ရာသီဥတုနဲ့လိုက်ဖက်တဲ့အဝတ်ကို ရွေးပါ။"
        )
    desc = (weather_desc or "").lower()
    if temperature_c is not None and temperature_c > 32:
        return _WEATHER_TIPS["hot"]
    if "rain" in desc or "drizzle" in desc or "thunderstorm" in desc:
        return _WEATHER_TIPS["rain"]
    if temperature_c is not None and temperature_c < 20:
        return _WEATHER_TIPS["cool"]
    if "humid" in desc:
        return _WEATHER_TIPS["humid"]
    # Hot but not extreme
    if temperature_c is not None and temperature_c > 28:
        return _WEATHER_TIPS["hot"]
    return (
        "ရာသီဥတုနဲ့လိုက်ဖက်တဲ့အဝတ်ကို ရွေးပါ။"
    )


def _occasion_my(occasion: str) -> str:
    """Translate an occasion key to natural Myanmar."""
    mapping: dict[str, str] = {
        "wedding": "မင်္ဂလာပွဲ",
        "work": "ရုံးသွား",
        "party": "ပါတီ",
        "date": "ချိန်းတွေ့",
        "casual": "အပြင်ထွက်",
        "interview": "အင်တာဗျူး",
        "sport": "အားကစား",
        "temple": "ဘုရားဖူး",
    }
    return mapping.get(occasion.lower().strip(), occasion)


# ── Suitability scoring ──────────────────────────────────

_SUITABILITY_THRESHOLD_HIGH = 45
_SUITABILITY_THRESHOLD_OK = 25


def _score_item(
    item: dict[str, Any],
    broad_type: str,
    occasion: str,
    temperature_c: float | None,
) -> int:
    """Score a single item for suitability to the occasion (0–100)."""
    cat = (item.get("category") or "").lower().strip()
    color = (item.get("color") or "").lower().strip()
    desc = (item.get("description") or "").lower().strip()
    occ_lower = occasion.lower().strip()
    score = 0

    # --- Occasion category fit ---
    if occ_lower == "interview":
        if broad_type in ("top", "bottom", "dress"):
            score += 35
        elif broad_type == "outerwear":
            score += 15
        else:
            score += 5
        # Colour discipline
        if _color_matches(color, _INTERVIEW_COLORS):
            score += 20
        elif _color_matches(color, _BRIGHT_ACCENT_COLORS):
            score -= 10  # Penalty for bright yellow/orange at interview
    elif occ_lower == "wedding":
        if broad_type in ("traditional", "dress"):
            score += 40
        elif broad_type == "top":
            score += 15
        elif broad_type == "bottom" and (
            "longyi" in cat or "longyi" in desc or "လုံချည်" in cat
        ):
            score += 25
        elif broad_type == "bottom":
            score += 10
        else:
            score += 5
        # Colour bonus
        if _color_matches(color, _WEDDING_COLORS):
            score += 15
    elif occ_lower == "party":
        # Party: prefer dress, then top+bottom.  Favors bold colors.
        if broad_type == "dress":
            score += 40
        elif broad_type in ("top", "bottom"):
            score += 20
        else:
            score += 10
        # Color bonus: red/black/gold > navy
        if _color_matches(color, _PARTY_COLORS):
            score += 25
        elif _color_matches(color, _INTERVIEW_COLORS):
            # Navy/beige/grey are fine but less exciting for party
            score += 8
        # Bright accent colors (yellow/orange) are OK for party
        if _color_matches(color, _BRIGHT_ACCENT_COLORS):
            score += 12
    elif occ_lower == "casual":
        if broad_type in ("top", "bottom", "dress"):
            score += 30
        else:
            score += 15
        # Hot weather: penalize heavy items
        if temperature_c and temperature_c > 28:
            heavy = ("wool", "fleece", "leather", "down", "puffer")
            if not any(kw in cat or kw in desc for kw in heavy):
                score += 10
    else:
        # Generic (work, date, sport, temple, etc.): prefer top/bottom/dress/traditional
        if broad_type in ("top", "bottom", "dress", "traditional"):
            score += 30
        else:
            score += 15

    # --- Description quality bonus ---
    if desc:
        score += 5

    return max(0, min(100, score))


# ── Main fallback generator ──────────────────────────────


def _best_from_scored(
    key: str,
    scored: dict[str, list[tuple[int, dict[str, Any]]]],
) -> dict[str, Any] | None:
    """Return the highest-scored item for *key* from *scored*, or None."""
    entries = scored.get(key, [])
    return entries[0][1] if entries else None


def _generate_fallback(
    wardrobe_items: list[dict[str, Any]],
    occasion: str,
    weather_desc: str | None = None,
    temperature_c: float | None = None,
    skin_tone: str | None = None,
    style_preference: str | None = None,
) -> dict[str, Any]:
    """Generate a rule-based outfit recommendation from wardrobe metadata.

    Guarantees valid outfit composition:
    • One dress only — OR —
    • One top + one bottom — OR —
    • One traditional/formal set
    • Optional: one outerwear or accessory

    Never returns dress+dress, top+top, bottom+bottom, or
    dress+top+bottom.

    Returns:
        Dict with ``outfit`` (list[str]), ``explanation`` (str),
        ``weather_based_tip`` (str), ``suitability`` (int 0–100).
    """
    if not wardrobe_items:
        return {
            "outfit": [],
            "explanation": "ဗီရိုထဲမှာ အဝတ်အစားမရှိသေးပါ။ ဓာတ်ပုံရိုက်ပြီး upload လုပ်ပါ။",
            "weather_based_tip": "",
        }

    occ_lower = occasion.lower().strip()

    # ── Classify all items ─────────────────────────────
    classified: dict[str, list[dict[str, Any]]] = {
        "dress": [], "top": [], "bottom": [], "traditional": [],
        "outerwear": [], "accessory": [], "shoes": [], "unknown": [],
    }
    for item in wardrobe_items:
        broad = _classify_item(item)
        if broad in classified:
            classified[broad].append(item)
        else:
            classified["unknown"].append(item)

    # Score each item
    scored: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for key, items in classified.items():
        scored[key] = sorted(
            ((_score_item(it, key, occasion, temperature_c), it) for it in items),
            key=lambda x: x[0],
            reverse=True,
        )

    outfit: list[str] = []
    explanation: str = ""
    suitability: int = 0

    # ── Select outfit based on occasion ─────────────────

    if occ_lower == "interview":
        outfit, explanation, suitability = _build_interview_outfit(
            classified, scored, occ_lower, temperature_c,
        )
    elif occ_lower == "wedding":
        outfit, explanation, suitability = _build_wedding_outfit(
            classified, scored, occ_lower, temperature_c,
        )
    elif occ_lower == "party":
        outfit, explanation, suitability = _build_party_outfit(
            classified, scored, occ_lower, temperature_c,
        )
    elif occ_lower == "casual":
        outfit, explanation, suitability = _build_casual_outfit(
            classified, scored, occ_lower, temperature_c,
        )
    else:
        outfit, explanation, suitability = _build_generic_outfit(
            classified, scored, occ_lower, temperature_c,
        )

    # ── Weather tip ────────────────────────────────────
    weather_tip = _get_weather_tip(weather_desc, temperature_c)

    return {
        "outfit": outfit,
        "explanation": explanation,
        "weather_based_tip": weather_tip,
    }


# ── Outfit builders (one per occasion type) ──────────────


def _build_interview_outfit(
    classified: dict[str, list[dict[str, Any]]],
    scored: dict[str, list[tuple[int, dict[str, Any]]]],
    occasion: str,
    temperature_c: float | None,
) -> tuple[list[str], str, int]:
    """Build an interview-appropriate outfit.

    Rules:
    • Prefer navy, white, beige, black, gray colours.
    • One top + one bottom, OR one formal dress.
    • Avoid bright yellow / orange.
    • Never return multiple tops.
    """
    _best = lambda k: _best_from_scored(k, scored)
    tops = scored.get("top", [])
    bottoms = scored.get("bottom", [])
    dresses = scored.get("dress", [])
    outerwear = scored.get("outerwear", [])
    occasion_my_str = _occasion_my(occasion)

    # ── Collect interview-colour-filtered items ──────────
    good_tops = [(s, it) for s, it in tops if _color_matches(
        it.get("color", ""), _INTERVIEW_COLORS)]
    good_dresses = [(s, it) for s, it in dresses if _color_matches(
        it.get("color", ""), _INTERVIEW_COLORS)]
    good_bottoms = [(s, it) for s, it in bottoms if _color_matches(
        it.get("color", ""), _INTERVIEW_COLORS)]

    # Try: formal dress in interview colour
    if good_dresses:
        s, dress = good_dresses[0]
        label = _item_label(dress)
        tip = ""
        if _best("outerwear"):
            ow = _best("outerwear")
            label_ow = _item_label(ow)
            label = f"{label} + {label_ow}"
        feasibility = s
        if feasibility >= _SUITABILITY_THRESHOLD_HIGH:
            explanation = (
                f"{occasion_my_str} အတွက် {label} က သပ်သပ်ရပ်ရပ်ဖြစ်ပြီး "
                f"ယုံကြည်မှုရှိရှိ ဝတ်လို့ရပါတယ်။"
            )
        else:
            explanation = (
                f"{occasion_my_str} အတွက် အနီးစပ်ဆုံးရွေးချယ်မှုပါ — "
                f"{label} ကို ဝတ်လို့ရပါတယ်။ "
                f"ဗီရိုထဲမှာ ဒီ occasion အတွက် item မလုံလောက်သေးပါ။"
            )
        return ([label], explanation, feasibility)

    # Try: top + bottom in interview colours
    if good_tops and good_bottoms:
        s_top, top = good_tops[0]
        s_bot, bottom = good_bottoms[0]
        label_top = _item_label(top)
        label_bot = _item_label(bottom)
        labels = [label_top, label_bot]
        feasibility = (s_top + s_bot) // 2

        # Optional outerwear
        if _best("outerwear"):
            ow = _best("outerwear")
            labels.append(_item_label(ow))

        if feasibility >= _SUITABILITY_THRESHOLD_HIGH:
            explanation = (
                f"{occasion_my_str} အတွက် {label_top} နဲ့ {label_bot} တွဲဝတ်တာက "
                f"သပ်သပ်ရပ်ရပ်ဖြစ်ပြီး ယုံကြည်မှုရှိစေပါတယ်။"
            )
        else:
            explanation = (
                f"{occasion_my_str} အတွက် အနီးစပ်ဆုံးရွေးချယ်မှုပါ — "
                f"{label_top} နဲ့ {label_bot} တွဲဝတ်လို့ရပါတယ်။ "
                f"ဗီရိုထဲမှာ ဒီ occasion အတွက် item မလုံလောက်သေးပါ။"
            )
        return (labels, explanation, feasibility)

    # Fallback: use any top + any bottom (but still not multiple tops)
    if tops and bottoms:
        s_top, top = tops[0]
        s_bot, bottom = bottoms[0]
        label_top = _item_label(top)
        label_bot = _item_label(bottom)
        labels = [label_top, label_bot]
        feasibility = (s_top + s_bot) // 2

        explanation = (
            f"{occasion_my_str} အတွက် အနီးစပ်ဆုံးရွေးချယ်မှုပါ — "
            f"{label_top} နဲ့ {label_bot} တွဲဝတ်လို့ရပါတယ်။ "
            f"ဒီ occasion အတွက် ဗီရိုထဲက item မလုံလောက်သေးပါ။ "
            f"သပ်သပ်ရပ်ရပ် အပေါ်ဝတ်နဲ့ အောက်ဝတ် ထည့်ပေးပါ။"
        )
        return (labels, explanation, feasibility)

    # Only dresses or only one category
    if dresses:
        s, dress = dresses[0]
        label = _item_label(dress)
        explanation = (
            f"{occasion_my_str} အတွက် အနီးစပ်ဆုံးရွေးချယ်မှုပါ — "
            f"{label} ကို ဝတ်လို့ရပါတယ်။ "
            f"ဒီ occasion အတွက် ဗီရိုထဲက item မလုံလောက်သေးပါ။"
        )
        return ([label], explanation, s)

    # Nothing useful
    return (
        [],
        f"{occasion_my_str} အတွက် သင့်တော်တဲ့ဝတ်စုံ ဗီရိုထဲမှာ မရှိသေးပါ။ "
        f"သပ်သပ်ရပ်ရပ် အပေါ်ဝတ်နဲ့ အောက်ဝတ် ထည့်ပေးပါ။",
        0,
    )


def _build_wedding_outfit(
    classified: dict[str, list[dict[str, Any]]],
    scored: dict[str, list[tuple[int, dict[str, Any]]]],
    occasion: str,
    temperature_c: float | None,
) -> tuple[list[str], str, int]:
    """Build a wedding-appropriate outfit.

    Rules:
    • Prefer traditional, longyi, formal dress, elegant dress.
    • Avoid casual top + bottom.
    • Avoid mixing dress + top + bottom.
    • If no wedding-appropriate item, say so honestly.
    """
    _best = lambda k: _best_from_scored(k, scored)
    traditionals = scored.get("traditional", [])
    dresses = scored.get("dress", [])
    tops = scored.get("top", [])
    bottoms = scored.get("bottom", [])
    outerwear = scored.get("outerwear", [])
    occasion_my_str = _occasion_my(occasion)

    # Best: traditional / longyi set
    if traditionals:
        s, trad = traditionals[0]
        label = _item_label(trad)
        # Try to complete with a longyi bottom if available
        longyi_bottoms = [(s, it) for s, it in bottoms
                          if "longyi" in (it.get("category") or "").lower()
                          or "လုံချည်" in (it.get("category") or "").lower()]
        if longyi_bottoms and "longyi" not in (trad.get("category") or "").lower():
            _, l_bot = longyi_bottoms[0]
            label = f"{label} + {_item_label(l_bot)}"
            feasibility = (s + longyi_bottoms[0][0]) // 2
        else:
            feasibility = s

        # Look for a matching top if traditional is a bottom
        if traditionals and any(
            kw in (traditionals[0][1].get("category") or "").lower()
            for kw in ("bottom", "longyi", "လုံချည်")
        ):
            nice_tops = [(s, it) for s, it in tops
                         if _color_matches(it.get("color", ""), _WEDDING_COLORS)]
            if nice_tops:
                _, n_top = nice_tops[0]
                label = f"{_item_label(n_top)} + {label}"

        if feasibility >= _SUITABILITY_THRESHOLD_HIGH:
            explanation = (
                f"{occasion_my_str} အတွက် {label} က "
                f"အလွန်သင့်တော်ပါတယ်။ မြန်မာဆန်ဆန် လှပစေပါတယ်။"
            )
        else:
            explanation = (
                f"{occasion_my_str} အတွက် {label} ကို ဝတ်လို့ရပါတယ်။ "
                f"အနီးစပ်ဆုံးရွေးချယ်မှုပါ။"
            )
        return ([label], explanation, feasibility)

    # Good: formal/elegant dress
    wedding_dresses = [(s, it) for s, it in dresses
                       if _color_matches(it.get("color", ""), _WEDDING_COLORS)]
    if wedding_dresses:
        s, dress = wedding_dresses[0]
        label = _item_label(dress)
        if _best("outerwear"):
            ow = _best("outerwear")
            label = f"{label} + {_item_label(ow)}"
        if s >= _SUITABILITY_THRESHOLD_HIGH:
            explanation = (
                f"{occasion_my_str} အတွက် {label} က သင့်တော်ပါတယ်။"
            )
        else:
            explanation = (
                f"{occasion_my_str} အတွက် အနီးစပ်ဆုံးရွေးချယ်မှုပါ — "
                f"{label} ကို ဝတ်လို့ရပါတယ်။"
            )
        return ([label], explanation, s)

    # OK: any dress
    if dresses:
        s, dress = dresses[0]
        label = _item_label(dress)
        explanation = (
            f"{occasion_my_str} အတွက် အနီးစပ်ဆုံးရွေးချယ်မှုပါ — "
            f"{label} ကို ဝတ်လို့ရပါတယ်။ "
            f"ဗီရိုထဲမှာ {occasion_my_str} အတွက် သင့်တဲ့ဝတ်စုံ မလုံလောက်သေးပါ။ "
            f"formal dress / မြန်မာဝတ်စုံ / longyi set တစ်ခုထည့်ပေးပါ။"
        )
        return ([label], explanation, s)

    # Poor: top + bottom (only if no dress/traditional at all)
    if tops and bottoms:
        s_top, top = tops[0]
        s_bot, bottom = bottoms[0]
        label_top = _item_label(top)
        label_bot = _item_label(bottom)
        labels = [label_top, label_bot]
        feasibility = (s_top + s_bot) // 2

        explanation = (
            f"{occasion_my_str} အတွက် အနီးစပ်ဆုံးရွေးချယ်မှုပါ — "
            f"{label_top} နဲ့ {label_bot} တွဲဝတ်လို့ရပါတယ်။ "
            f"ဒါပေမယ့် {occasion_my_str} အတွက် ပိုသပ်ရပ်တဲ့ "
            f"မြန်မာဝတ်စုံ သို့မဟုတ် formal ဝတ်စုံလိုပါမယ်။"
        )
        return (labels, explanation, feasibility)

    # Nothing suitable
    return (
        [],
        f"ဗီရိုထဲမှာ {occasion_my_str} အတွက် သင့်တဲ့ဝတ်စုံ မလုံလောက်သေးပါ။ "
        f"formal dress / မြန်မာဝတ်စုံ / longyi set တစ်ခုထည့်ပေးပါ။",
        0,
    )


def _build_party_outfit(
    classified: dict[str, list[dict[str, Any]]],
    scored: dict[str, list[tuple[int, dict[str, Any]]]],
    occasion: str,
    temperature_c: float | None,
) -> tuple[list[str], str, int]:
    """Build a party-appropriate outfit.

    Rules:
    • Prefer red dress, black dress, elegant dress over navy.
    • If red dress exists, explain why it's the best party choice.
    • One dress, OR one top + one bottom.
    • Avoid recommending navy when a bolder option is available.
    """
    _best = lambda k: _best_from_scored(k, scored)
    tops = scored.get("top", [])
    bottoms = scored.get("bottom", [])
    dresses = scored.get("dress", [])
    occasion_my_str = _occasion_my(occasion)

    # ── Party dress selection: favours bold colors ─────────
    # Separate dresses into bold (red/black/gold) and neutral (navy/beige)
    bold_dresses = [(s, it) for s, it in dresses
                    if _color_matches(it.get("color", ""), _PARTY_COLORS)]
    other_dresses = [(s, it) for s, it in dresses
                     if not _color_matches(it.get("color", ""), _PARTY_COLORS)]

    # Best: bold party dress
    if bold_dresses:
        s, dress = bold_dresses[0]
        label = _item_label(dress)
        if _best("outerwear"):
            ow = _best("outerwear")
            label = f"{label} + {_item_label(ow)}"
        dress_color = (dress.get("color") or "").lower()
        if dress_color in ("red", "အနီ"):
            explanation = (
                f"ပါတီအတွက် {label} က ပိုထင်ရှားပြီး "
                f"ပွဲတက် look နဲ့ ပိုလိုက်ပါတယ်။"
            )
        else:
            explanation = (
                f"ပါတီအတွက် {label} က "
                f"ထင်ရှားပြီး ကြော့ရှင်းတဲ့ look ဖြစ်ပါတယ်။"
            )
        return ([label], explanation, s)

    # OK: any dress (but note if navy is less ideal)
    if dresses:
        s, dress = dresses[0]
        label = _item_label(dress)
        dress_color = (dress.get("color") or "").lower()
        if dress_color in ("navy", "နေပယ်ပြာ", "blue", "beige", "gray", "grey"):
            explanation = (
                f"{label} က ပါတီအတွက် ဝတ်လို့ရပေမယ့် "
                f"အနီရောင် သို့မဟုတ် အနက်ရောင် "
                f"တစ်ဆက်တည်းဝတ်စုံဆိုရင် ပိုထင်ရှားပါမယ်။"
            )
        else:
            explanation = (
                f"ပါတီအတွက် {label} က သင့်တော်ပါတယ်။"
            )
        return ([label], explanation, s)

    # Fallback: top + bottom
    if tops and bottoms:
        s_top, top = tops[0]
        s_bot, bottom = bottoms[0]
        label_top = _item_label(top)
        label_bot = _item_label(bottom)
        labels = [label_top, label_bot]
        feasibility = (s_top + s_bot) // 2
        explanation = (
            f"ပါတီအတွက် {label_top} နဲ့ {label_bot} တွဲဝတ်လို့ရပါတယ်။ "
            f"ဒါပေမယ့် ပါတီအတွက် အနီရောင် သို့မဟုတ် အနက်ရောင် "
            f"တစ်ဆက်တည်းဝတ်စုံဆိုရင် ပိုကြော့ပါမယ်။"
        )
        return (labels, explanation, feasibility)

    return (
        [],
        f"ပါတီအတွက် သင့်တော်တဲ့ဝတ်စုံ ဗီရိုထဲမှာ မရှိသေးပါ। "
        f"အနီရောင် သို့မဟုတ် အနက်ရောင် တစ်ဆက်တည်းဝတ်စုံ ထည့်ပေးပါ။",
        0,
    )


def _build_casual_outfit(
    classified: dict[str, list[dict[str, Any]]],
    scored: dict[str, list[tuple[int, dict[str, Any]]]],
    occasion: str,
    temperature_c: float | None,
) -> tuple[list[str], str, int]:
    """Build a casual outfit.

    Rules:
    • One comfortable top + one bottom.
    • Prefer breathable colours / fabrics if hot.
    """
    tops = scored.get("top", [])
    bottoms = scored.get("bottom", [])
    dresses = scored.get("dress", [])
    occasion_my_str = _occasion_my(occasion)

    is_hot = temperature_c is not None and temperature_c > 28

    # Prefer top + bottom
    if tops and bottoms:
        s_top, top = tops[0]
        s_bot, bottom = bottoms[0]
        label_top = _item_label(top)
        label_bot = _item_label(bottom)
        labels = [label_top, label_bot]
        feasibility = (s_top + s_bot) // 2

        if is_hot:
            explanation = (
                f"{occasion_my_str} အတွက် {label_top} နဲ့ {label_bot} တွဲဝတ်တာက "
                f"သက်တောင့်သက်သာရှိပါတယ်။ "
                f"ရာသီဥတုပူလို့ ပေါ့ပါးပြီး လေဝင်လေထွက်ကောင်းတဲ့အဝတ်ကို ရွေးပါ။"
            )
        else:
            explanation = (
                f"{occasion_my_str} အတွက် {label_top} နဲ့ {label_bot} တွဲဝတ်တာက "
                f"သက်တောင့်သက်သာရှိပြီး လှပပါတယ်။"
            )
        return (labels, explanation, feasibility)

    # Fallback: dress
    if dresses:
        s, dress = dresses[0]
        label = _item_label(dress)
        if is_hot:
            explanation = (
                f"{occasion_my_str} အတွက် {label} က "
                f"သက်တောင့်သက်သာရှိပြီး လှပပါတယ်။ "
                f"ရာသီဥတုပူလို့ ပေါ့ပါးတဲ့အထည်ကို ရွေးပါ။"
            )
        else:
            explanation = (
                f"{occasion_my_str} အတွက် {label} က "
                f"သက်တောင့်သက်သာရှိပြီး လှပပါတယ်။"
            )
        return ([label], explanation, s)

    # Only tops or only bottoms
    if tops:
        s, top = tops[0]
        label = _item_label(top)
        return (
            [label],
            f"{occasion_my_str} အတွက် အနီးစပ်ဆုံးရွေးချယ်မှုပါ — "
            f"{label} ကို ဝတ်လို့ရပါတယ်။ အောက်ဝတ်လည်း ထည့်ပေးပါ။",
            s,
        )
    if bottoms:
        s, bottom = bottoms[0]
        label = _item_label(bottom)
        return (
            [label],
            f"{occasion_my_str} အတွက် အနီးစပ်ဆုံးရွေးချယ်မှုပါ — "
            f"{label} ကို ဝတ်လို့ရပါတယ်။ အပေါ်ဝတ်လည်း ထည့်ပေးပါ။",
            s,
        )

    return (
        [],
        f"{occasion_my_str} အတွက် သင့်တော်တဲ့ဝတ်စုံ ဗီရိုထဲမှာ မရှိသေးပါ။",
        0,
    )


def _build_generic_outfit(
    classified: dict[str, list[dict[str, Any]]],
    scored: dict[str, list[tuple[int, dict[str, Any]]]],
    occasion: str,
    temperature_c: float | None,
) -> tuple[list[str], str, int]:
    """Build an outfit for generic/other occasions.

    Rules:
    • Prefer: one dress, OR one top + one bottom, OR one traditional set.
    • Optional outerwear/accessory.
    • Never invalid combinations.
    """
    tops = scored.get("top", [])
    bottoms = scored.get("bottom", [])
    dresses = scored.get("dress", [])
    traditionals = scored.get("traditional", [])
    occasion_my_str = _occasion_my(occasion)

    # Best: traditional
    if traditionals:
        s, trad = traditionals[0]
        label = _item_label(trad)
        return (
            [label],
            f"{occasion_my_str} အတွက် {label} က သင့်တော်ပါတယ်။",
            s,
        )

    # Good: dress
    if dresses:
        s, dress = dresses[0]
        label = _item_label(dress)
        return (
            [label],
            f"{occasion_my_str} အတွက် {label} က သင့်တော်ပါတယ်။",
            s,
        )

    # Good: top + bottom
    if tops and bottoms:
        s_top, top = tops[0]
        s_bot, bottom = bottoms[0]
        label_top = _item_label(top)
        label_bot = _item_label(bottom)
        labels = [label_top, label_bot]
        feasibility = (s_top + s_bot) // 2

        return (
            labels,
            f"{occasion_my_str} အတွက် {label_top} နဲ့ {label_bot} တွဲဝတ်တာက "
            f"သင့်တော်ပါတယ်။",
            feasibility,
        )

    # Only tops
    if tops:
        s, top = tops[0]
        label = _item_label(top)
        return (
            [label],
            f"{occasion_my_str} အတွက် အနီးစပ်ဆုံးရွေးချယ်မှုပါ — "
            f"{label} ကို ဝတ်လို့ရပါတယ်။ အောက်ဝတ်လည်း ထည့်ပေးပါ။",
            s,
        )

    # Only bottoms
    if bottoms:
        s, bottom = bottoms[0]
        label = _item_label(bottom)
        return (
            [label],
            f"{occasion_my_str} အတွက် အနီးစပ်ဆုံးရွေးချယ်မှုပါ — "
            f"{label} ကို ဝတ်လို့ရပါတယ်။ အပေါ်ဝတ်လည်း ထည့်ပေးပါ။",
            s,
        )

    return (
        [],
        f"{occasion_my_str} အတွက် သင့်တော်တဲ့ဝတ်စုံ ဗီရိုထဲမှာ မရှိသေးပါ။",
        0,
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
