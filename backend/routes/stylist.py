"""Stylist routes: get outfit recommendations, chat, and view history.

Endpoints
    POST /stylist/recommend        —  AI-powered outfit recommendation.
    POST /stylist/chat             —  General chat with AI stylist.
    GET  /stylist/history/{user_id} —  List past style sessions.

Requires authentication on all endpoints.
"""

import json
import logging
import random
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models import User, Profile, Wardrobe, StyleSession
from routes.auth import get_current_user
from services.weather_svc import get_current_weather, WeatherData
from services.openai_svc import get_outfit_recommendation as openai_recommend
from services.gemini_svc import get_outfit_recommendation as gemini_recommend
from services.gemini_svc import get_chat_response
from services.openai_svc import get_chat_response as openai_chat
from services.openrouter_svc import get_chat_response as openrouter_chat
from services.gemini_svc import analyze_clothing_image
from services.gemini_svc import FASHION_KNOWLEDGE, APP_GUIDE
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


class ChatRequest(BaseModel):
    """Payload for POST /stylist/chat — general conversation."""

    message: str = Field(
        ..., min_length=1, max_length=500,
        description="User's chat message",
    )
    conversation_history: list[dict[str, str]] = Field(
        default_factory=list,
        description='Previous messages as [{"role": "user"|"bot", "content": "..."}]',
    )


class AnalyzeRequest(BaseModel):
    """Payload for POST /stylist/analyze — send image for vision analysis."""

    image_data: str = Field(
        ..., min_length=100,
        description="Base64-encoded image data",
    )
    mime_type: str = Field(
        default="image/jpeg",
        description="MIME type of the image",
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

    Uses both category and subtype for accurate classification.
    A ``jean coat`` subtype with ``outerwear`` category stays outerwear.
    A ``mini skirt`` subtype with ``bottom`` category stays bottom.
    """
    cat = (item.get("category") or "").lower().strip()
    sub = (item.get("subtype") or "").lower().strip()
    desc = (item.get("description") or "").lower().strip()
    combined = f"{cat} {sub} {desc}"

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

    # Fallback: try subtype first, then description
    if any(kw in sub for kw in _DRESS_KEYWORDS):
        return "dress"
    if any(kw in sub for kw in _TOP_KEYWORDS):
        return "top"
    if any(kw in sub for kw in _BOTTOM_KEYWORDS):
        return "bottom"
    if any(kw in combined for kw in _DRESS_KEYWORDS):
        return "dress"
    if any(kw in combined for kw in _TOP_KEYWORDS):
        return "top"
    if any(kw in combined for kw in _BOTTOM_KEYWORDS):
        return "bottom"

    return "unknown"


def _has_subtype(item: dict[str, Any], *keywords: str) -> bool:
    """Check whether an item's subtype or category matches any of *keywords*."""
    sub = (item.get("subtype") or "").lower().strip()
    cat = (item.get("category") or "").lower().strip()
    combined = f"{sub} {cat}"
    return any(kw in combined for kw in keywords)


def _color_matches(color: str, allowed: set[str]) -> bool:
    """Check whether *color* belongs to *allowed* set (case-insensitive)."""
    if not color:
        return False
    return color.lower().strip() in allowed


def _item_label(item: dict[str, Any]) -> str:
    """Build a human-readable Myanmar label for a wardrobe item.

    Uses subtype for specific labels when available:
        blouse     → blouse / ဘလောက်စ်
        jeans      → jeans / ဂျင်းဘောင်းဘီ
        mini skirt → mini skirt / စကတ်တို
        party dress → ပွဲတက်ဂါဝန်
        longyi     → လုံချည်
        etc.

    Falls back to broad category label when subtype is empty.
    Never duplicates category text.
    """
    cat = item.get("category") or ""
    sub = (item.get("subtype") or "").lower().strip()
    color = item.get("color") or ""
    desc = item.get("description") or ""

    # ── Subtype → Myanmar label map (specific, human-friendly) ──
    subtype_label_map: dict[str, str] = {
        # Tops
        "blouse": "blouse / ဘလောက်စ်",
        "shirt": "shirt / ရှပ်အင်္ကျီ",
        "t-shirt": "t-shirt / တီရှပ်",
        "sweater": "sweater / ဆွယ်တာ",
        "hoodie": "hoodie / ဟူဒီ",
        "blazer": "blazer / ဘလေဇာ",
        "polo": "polo / ပိုလို",
        "tank top": "tank top / တန့်ခ်တော့ပ်",
        # Bottoms
        "jeans": "jeans / ဂျင်းဘောင်းဘီ",
        "skirt": "skirt / စကတ်",
        "mini skirt": "mini skirt / စကတ်တို",
        "trousers": "trousers / ဘောင်းဘီရှည်",
        "shorts": "shorts / ဘောင်းဘီတို",
        "cargo pants": "cargo pants / ကာဂိုဘောင်းဘီ",
        # Dresses
        "party dress": "ပွဲတက်ဂါဝန်",
        "formal dress": "formal dress / ဖောင်မယ်ဂါဝန်",
        "casual dress": "casual dress / ပေါ့ပေါ့ပါးပါးဂါဝန်",
        "maxi dress": "maxi dress / မက်စီဂါဝန်",
        "mini dress": "mini dress / မီနီဂါဝန်",
        # Outerwear
        "jean coat": "jean coat / ဂျင်းအပေါ်ထပ်",
        "jacket": "jacket / အပေါ်ထပ်",
        "coat": "coat / ကုတ်အင်္ကျီ",
        "cardigan": "cardigan / ကာဒီဂန်",
        "shawl": "shawl / ပဝါ",
        # Traditional
        "longyi": "လုံချည်",
        "htamein": "ထဘီ",
        "taikpon": "တိုက်ပုံ",
    }

    # ── Category → Myanmar label map (fallback) ──
    cat_my_map: dict[str, str] = {
        "top": "အပေါ်ဝတ်", "bottom": "အောက်ဝတ်", "dress": "တစ်ဆက်တည်းဝတ်စုံ",
        "outerwear": "အပေါ်ထပ်", "accessory": "အသုံးအဆောင်", "shoes": "ဖိနပ်",
        "traditional": "မြန်မာဝတ်စုံ", "longyi": "လုံချည်",
        "shirt": "အပေါ်ဝတ်", "blouse": "အပေါ်ဝတ်", "t-shirt": "အပေါ်ဝတ်",
        "sweater": "အပေါ်ဝတ်", "hoodie": "အပေါ်ဝတ်", "blazer": "အပေါ်ထပ်",
        "jacket": "အပေါ်ထပ်",
        "trousers": "အောက်ဝတ်", "pants": "အောက်ဝတ်", "jeans": "အောက်ဝတ်",
        "shorts": "အောက်ဝတ်", "skirt": "အောက်ဝတ်",
        "gown": "တစ်ဆက်တည်းဝတ်စုံ", "jumpsuit": "တစ်ဆက်တည်းဝတ်စုံ",
        "coat": "အပေါ်ထပ်", "cardigan": "အပေါ်ထပ်",
        # Myanmar self-keys — prevent duplication when DB stores Myanmar text
        "အပေါ်ဝတ်": "အပေါ်ဝတ်", "အောက်ဝတ်": "အောက်ဝတ်",
        "တစ်ဆက်တည်းဝတ်စုံ": "တစ်ဆက်တည်းဝတ်စုံ", "ဂါဝန်": "တစ်ဆက်တည်းဝတ်စုံ",
        "အပေါ်ထပ်": "အပေါ်ထပ်", "ဖိနပ်": "ဖိနပ်",
        "အသုံးအဆောင်": "အသုံးအဆောင်",
        "မြန်မာဝတ်စုံ": "မြန်မာဝတ်စုံ", "လုံချည်": "လုံချည်",
        "အင်္ကျီ": "အပေါ်ဝတ်", "ဘောင်းဘီ": "အောက်ဝတ်",
        "ထဘီ": "မြန်မာဝတ်စုံ",
    }

    # Build the base label — prefer subtype label, fall back to category label
    if sub and sub in subtype_label_map:
        base = subtype_label_map[sub]
    else:
        cat_key = cat.lower().strip() if cat else ""
        base = cat_my_map.get(cat_key, cat)

    # Append color and description
    if color:
        base = f"{base} · {color}"
    if desc:
        base = f"{base} — {desc}"
    return base

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
    style_preference: str | None = None,
) -> int:
    """Score a single item for suitability to the occasion (0–100).

    Scoring dimensions:
    • Occasion–category fit (with subtype bonus/penalty)
    • Colour discipline (occasion-appropriate, no over-bonus for red/navy)
    • Style preference alignment (small bonus)
    • Weather suitability
    • Description quality
    """
    cat = (item.get("category") or "").lower().strip()
    sub = (item.get("subtype") or "").lower().strip()
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
        # Colour: modest bonus for interview-appropriate colours
        if _color_matches(color, _INTERVIEW_COLORS):
            score += 10
        elif _color_matches(color, _BRIGHT_ACCENT_COLORS):
            score -= 10
        # Subtype: mini skirt penalty for interview
        if "mini skirt" in sub:
            score -= 15
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
            score += 8
        # Subtype bonuses for wedding
        if sub in ("formal dress", "longyi", "htamein", "taikpon"):
            score += 15
    elif occ_lower == "party":
        # Party: prefer dress, then top+bottom
        if broad_type == "dress":
            score += 40
        elif broad_type in ("top", "bottom"):
            score += 20
        else:
            score += 10
        # Color bonus
        if _color_matches(color, _PARTY_COLORS):
            score += 12
        elif _color_matches(color, _INTERVIEW_COLORS):
            score += 5
        if _color_matches(color, _BRIGHT_ACCENT_COLORS):
            score += 8
        # Subtype: party dress gets significant bonus
        if sub in ("party dress", "mini dress"):
            score += 15
        # Mini skirt ok for party
        if "mini skirt" in sub:
            score += 5
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
        # Light/bright colors feel more casual
        light_colors = {"white", "beige", "cream", "pink", "yellow",
                        "အဖြူ", "ဘဲဂျီ", "ပန်းရောင်", "အဝါ"}
        if _color_matches(color, light_colors):
            score += 3
        # Subtype: casual-friendly items get bonus
        if sub in ("blouse", "t-shirt", "jeans", "shorts", "casual dress"):
            score += 5
    else:
        # Generic (work, date, sport, temple, etc.)
        if broad_type in ("top", "bottom", "dress", "traditional"):
            score += 30
        else:
            score += 15

    # --- Style preference bonus (small, 0–5) ---
    if style_preference:
        sp = style_preference.lower().strip()
        if sp == "formal" and broad_type in ("dress", "traditional", "outerwear"):
            score += 5
        elif sp == "casual" and broad_type in ("top", "bottom"):
            score += 5
        elif sp == "traditional" and broad_type == "traditional":
            score += 5
        elif sp == "sporty" and broad_type in ("top", "bottom", "shoes"):
            score += 3

    # --- Description quality bonus ---
    if desc:
        score += 5

    return max(0, min(100, score))
def _best_from_scored(
    key: str,
    scored: dict[str, list[tuple[int, dict[str, Any]]]],
) -> dict[str, Any] | None:
    """Return the highest-scored item for *key* from *scored*, or None.

    When multiple items share the top score, one is picked at random
    so the recommendation varies naturally across calls.
    """
    return _pick_best(scored.get(key, []))


def _pick_best(
    entries: list[tuple[int, dict[str, Any]]],
    margin: int = 5,
) -> dict[str, Any] | None:
    """Pick the best item from scored *entries*, with tie-breaker variety.

    All items within *margin* points of the top score are considered
    equally suitable; one is chosen at random.  This prevents always
    recommending the same red/navy item when several are equally good.
    """
    if not entries:
        return None
    top_score = entries[0][0]
    # Collect items within margin of the top score
    candidates = [it for s, it in entries if s >= top_score - margin]
    return random.choice(candidates) if candidates else entries[0][1]


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

    # Try: formal dress in interview colour (randomised among top picks)
    if good_dresses:
        dress = _pick_best(good_dresses)
        s = good_dresses[0][0]  # top score for feasibility check
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

    # Try: top + bottom in interview colours (randomised)
    if good_tops and good_bottoms:
        top = _pick_best(good_tops)
        bottom = _pick_best(good_bottoms)
        s_top = good_tops[0][0]
        s_bot = good_bottoms[0][0]
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

    # Fallback: use any top + any bottom (randomised, but still not multiple tops)
    if tops and bottoms:
        top = _pick_best(tops)
        bottom = _pick_best(bottoms)
        s_top = tops[0][0]
        s_bot = bottoms[0][0]
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
        dress = _pick_best(dresses)
        s = dresses[0][0]
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

    # Best: traditional / longyi set (randomised among top picks)
    if traditionals:
        trad = _pick_best(traditionals)
        s = traditionals[0][0]
        label = _item_label(trad)
        # Try to complete with a longyi bottom if available
        longyi_bottoms = [(s, it) for s, it in bottoms
                          if "longyi" in (it.get("category") or "").lower()
                          or "လုံချည်" in (it.get("category") or "").lower()]
        if longyi_bottoms and "longyi" not in (trad.get("category") or "").lower():
            l_bot = _pick_best(longyi_bottoms)
            label = f"{label} + {_item_label(l_bot)}"
            feasibility = (s + longyi_bottoms[0][0]) // 2
        else:
            feasibility = s

        # Look for a matching top if traditional is a bottom
        if any(
            kw in (trad.get("category") or "").lower()
            for kw in ("bottom", "longyi", "လုံချည်")
        ):
            nice_tops = [(s, it) for s, it in tops
                         if _color_matches(it.get("color", ""), _WEDDING_COLORS)]
            if nice_tops:
                n_top = _pick_best(nice_tops)
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

    # Good: formal/elegant dress (randomised)
    wedding_dresses = [(s, it) for s, it in dresses
                       if _color_matches(it.get("color", ""), _WEDDING_COLORS)]
    if wedding_dresses:
        dress = _pick_best(wedding_dresses)
        s = wedding_dresses[0][0]
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

    # OK: any dress (randomised)
    if dresses:
        dress = _pick_best(dresses)
        s = dresses[0][0]
        label = _item_label(dress)
        explanation = (
            f"{occasion_my_str} အတွက် အနီးစပ်ဆုံးရွေးချယ်မှုပါ — "
            f"{label} ကို ဝတ်လို့ရပါတယ်။ "
            f"ဗီရိုထဲမှာ {occasion_my_str} အတွက် သင့်တဲ့ဝတ်စုံ မလုံလောက်သေးပါ။ "
            f"formal dress / မြန်မာဝတ်စုံ / longyi set တစ်ခုထည့်ပေးပါ။"
        )
        return ([label], explanation, s)

    # Poor: top + bottom (randomised, only if no dress/traditional)
    if tops and bottoms:
        top = _pick_best(tops)
        bottom = _pick_best(bottoms)
        s_top = tops[0][0]
        s_bot = bottoms[0][0]
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
    • Prefer party dress over other dresses.
    • Prefer bold red/black dress over navy dress.
    • If no dress: blouse + skirt or top + bottom.
    • Mini skirt is acceptable for party.
    • One dress, OR one top + one bottom + optional outerwear.
    """
    _best = lambda k: _best_from_scored(k, scored)
    tops = scored.get("top", [])
    bottoms = scored.get("bottom", [])
    dresses = scored.get("dress", [])
    occasion_my_str = _occasion_my(occasion)

    # ── Separate party-specific dresses from general dresses ──
    party_dress_subtypes = {"party dress", "mini dress"}
    party_dresses = [(s, it) for s, it in dresses
                     if _has_subtype(it, *party_dress_subtypes)]
    bold_dresses = [(s, it) for s, it in dresses
                    if _color_matches(it.get("color", ""), _PARTY_COLORS)
                    and not _has_subtype(it, *party_dress_subtypes)]

    # Best: party dress subtype (e.g. party dress, mini dress)
    if party_dresses:
        dress = _pick_best(party_dresses)
        s = party_dresses[0][0]
        label = _item_label(dress)
        if _best("outerwear"):
            ow = _best("outerwear")
            label = f"{label} + {_item_label(ow)}"
        explanation = (
            f"ပါတီအတွက် {label} က ထင်ရှားပြီး ကြော့ရှင်းတဲ့ look ဖြစ်ပါတယ်။"
        )
        return ([label], explanation, s)

    # Good: bold party dress (red, black, etc.)
    if bold_dresses:
        dress = _pick_best(bold_dresses)
        s = bold_dresses[0][0]
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

    # OK: any dress
    if dresses:
        dress = _pick_best(dresses)
        s = dresses[0][0]
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

    # Fallback: top + bottom (prefer blouse + skirt for party)
    if tops and bottoms:
        # Try to pick party-friendly combos: blouse+skirt is better than t-shirt+jeans
        top = _pick_best(tops)
        bottom = _pick_best(bottoms)
        s_top = tops[0][0]
        s_bot = bottoms[0][0]
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
        f"ပါတီအတွက် သင့်တော်တဲ့ဝတ်စုံ ဗီရိုထဲမှာ မရှိသေးပါ။ "
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
    • Prefer comfortable top + bottom combos: blouse+jeans, t-shirt+skirt, top+jeans.
    • Optional outerwear (jean coat, jacket) but never as a standalone item.
    • Dress is a fallback if no top+bottom combo exists.
    • Hot weather: prefer light colors and breathable items.
    """
    tops = scored.get("top", [])
    bottoms = scored.get("bottom", [])
    dresses = scored.get("dress", [])
    outerwear = scored.get("outerwear", [])
    occasion_my_str = _occasion_my(occasion)

    is_hot = temperature_c is not None and temperature_c > 28

    # Prefer top + bottom (with optional outerwear)
    if tops and bottoms:
        top = _pick_best(tops)
        bottom = _pick_best(bottoms)
        s_top = tops[0][0]
        s_bot = bottoms[0][0]
        label_top = _item_label(top)
        label_bot = _item_label(bottom)
        labels = [label_top, label_bot]
        feasibility = (s_top + s_bot) // 2

        # Optional outerwear — jean coat/jacket should only be outerwear, not main
        outer = _best_from_scored("outerwear", scored)
        if outer:
            labels.append(_item_label(outer))

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
        dress = _pick_best(dresses)
        s = dresses[0][0]
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
        top = _pick_best(tops)
        s = tops[0][0]
        label = _item_label(top)
        return (
            [label],
            f"{occasion_my_str} အတွက် အနီးစပ်ဆုံးရွေးချယ်မှုပါ — "
            f"{label} ကို ဝတ်လို့ရပါတယ်။ အောက်ဝတ်လည်း ထည့်ပေးပါ။",
            s,
        )
    if bottoms:
        bottom = _pick_best(bottoms)
        s = bottoms[0][0]
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
    • Date/coffee date: prefer casual top+bottom (NOT traditional).
    • Wedding: prefer traditional first.
    • Other: top+bottom first, then dress, then traditional.
    • Optional outerwear/accessory.
    • Never invalid combinations.
    """
    tops = scored.get("top", [])
    bottoms = scored.get("bottom", [])
    dresses = scored.get("dress", [])
    traditionals = scored.get("traditional", [])
    occasion_my_str = _occasion_my(occasion)
    occ_lower = occasion.lower().strip()

    # ── Date/coffee date: prefer casual top+bottom, NOT traditional ──
    if occ_lower in ("date", "coffee date", "coffee_date"):
        if tops and bottoms:
            top = _pick_best(tops)
            bottom = _pick_best(bottoms)
            s_top = tops[0][0]
            s_bot = bottoms[0][0]
            label_top = _item_label(top)
            label_bot = _item_label(bottom)
            labels = [label_top, label_bot]
            feasibility = (s_top + s_bot) // 2
            explanation = (
                f"{occasion_my_str} အတွက် {label_top} နဲ့ {label_bot} တွဲဝတ်တာက "
                f"သက်တောင့်သက်သာရှိပြီး လှပပါတယ်။ "
                f"ရိုးရှင်းပြီး clean look က date အတွက် အကောင်းဆုံးပါ။"
            )
            return (labels, explanation, feasibility)
        if dresses:
            dress = _pick_best(dresses)
            s = dresses[0][0]
            label = _item_label(dress)
            return (
                [label],
                f"{occasion_my_str} အတွက် {label} က သက်တောင့်သက်သာရှိပြီး လှပပါတယ်။",
                s,
            )

    # ── Wedding: prefer traditional first ──
    if occ_lower == "wedding" and traditionals:
        trad = _pick_best(traditionals)
        s = traditionals[0][0]
        label = _item_label(trad)
        return (
            [label],
            f"{occasion_my_str} အတွက် {label} က သင့်တော်ပါတယ်။",
            s,
        )

    # ── Default: top + bottom first (most versatile) ──
    if tops and bottoms:
        top = _pick_best(tops)
        bottom = _pick_best(bottoms)
        s_top = tops[0][0]
        s_bot = bottoms[0][0]
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

    # Then: dress
    if dresses:
        dress = _pick_best(dresses)
        s = dresses[0][0]
        label = _item_label(dress)
        return (
            [label],
            f"{occasion_my_str} အတွက် {label} က သင့်တော်ပါတယ်။",
            s,
        )

    # Then: traditional
    if traditionals:
        trad = _pick_best(traditionals)
        s = traditionals[0][0]
        label = _item_label(trad)
        return (
            [label],
            f"{occasion_my_str} အတွက် {label} က သင့်တော်ပါတယ်။",
            s,
        )

    # Only tops (randomised)
    if tops:
        top = _pick_best(tops)
        s = tops[0][0]
        label = _item_label(top)
        return (
            [label],
            f"{occasion_my_str} အတွက် အနီးစပ်ဆုံးရွေးချယ်မှုပါ — "
            f"{label} ကို ဝတ်လို့ရပါတယ်။ အောက်ဝတ်လည်း ထည့်ပေးပါ။",
            s,
        )

    # Only bottoms (randomised)
    if bottoms:
        bottom = _pick_best(bottoms)
        s = bottoms[0][0]
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



# ── General Fashion Advice (no wardrobe) ─────────────────


# ── Routes ─────────────────────────────────────────────


# ── Demo wardrobe items for live demo ──────────────────
_DEMO_WARDROBE_ITEMS: list[dict[str, Any]] = [
    {
        "cloudinary_url": "https://res.cloudinary.com/demo/image/upload/v1/sample.jpg",
        "cloudinary_public_id": "demo-navy-blazer",
        "category": "top",
        "subtype": "blazer",
        "color": "navy",
        "description": "Classic navy blazer, perfect for formal occasions",
        "style_tags": "formal,classic,versatile",
        "material_tags": "wool blend",
        "occasion_tags": "interview,wedding,work",
    },
    {
        "cloudinary_url": "https://res.cloudinary.com/demo/image/upload/v1/sample.jpg",
        "cloudinary_public_id": "demo-white-shirt",
        "category": "top",
        "subtype": "shirt",
        "color": "white",
        "description": "Crisp white cotton shirt",
        "style_tags": "formal,clean,minimal",
        "material_tags": "cotton",
        "occasion_tags": "interview,work,wedding",
    },
    {
        "cloudinary_url": "https://res.cloudinary.com/demo/image/upload/v1/sample.jpg",
        "cloudinary_public_id": "demo-beige-chinos",
        "category": "bottom",
        "subtype": "trousers",
        "color": "beige",
        "description": "Slim-fit beige chinos",
        "style_tags": "smart-casual,versatile",
        "material_tags": "cotton",
        "occasion_tags": "work,casual,date",
    },
    {
        "cloudinary_url": "https://res.cloudinary.com/demo/image/upload/v1/sample.jpg",
        "cloudinary_public_id": "demo-red-dress",
        "category": "dress",
        "subtype": "party dress",
        "color": "red",
        "description": "Elegant red party dress",
        "style_tags": "party,elegant,bold",
        "material_tags": "silk blend",
        "occasion_tags": "party,wedding,date",
    },
    {
        "cloudinary_url": "https://res.cloudinary.com/demo/image/upload/v1/sample.jpg",
        "cloudinary_public_id": "demo-casual-tee",
        "category": "top",
        "subtype": "t-shirt",
        "color": "white",
        "description": "Relaxed-fit white cotton tee",
        "style_tags": "casual,comfortable,everyday",
        "material_tags": "cotton",
        "occasion_tags": "casual,sport",
    },
    {
        "cloudinary_url": "https://res.cloudinary.com/demo/image/upload/v1/sample.jpg",
        "cloudinary_public_id": "demo-jeans",
        "category": "bottom",
        "subtype": "jeans",
        "color": "blue",
        "description": "Classic blue denim jeans",
        "style_tags": "casual,classic,versatile",
        "material_tags": "denim",
        "occasion_tags": "casual,date",
    },
    {
        "cloudinary_url": "https://res.cloudinary.com/demo/image/upload/v1/sample.jpg",
        "cloudinary_public_id": "demo-longyi",
        "category": "traditional",
        "subtype": "longyi",
        "color": "green",
        "description": "Traditional Myanmar longyi for formal events",
        "style_tags": "traditional,formal,cultural",
        "material_tags": "silk",
        "occasion_tags": "wedding,temple",
    },
    {
        "cloudinary_url": "https://res.cloudinary.com/demo/image/upload/v1/sample.jpg",
        "cloudinary_public_id": "demo-leather-bag",
        "category": "accessory",
        "subtype": "bag",
        "color": "brown",
        "description": "Brown leather crossbody bag",
        "style_tags": "classic,practical",
        "material_tags": "leather",
        "occasion_tags": "work,casual,date",
    },
]


@router.post("/seed-demo")
def seed_demo_wardrobe(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuthResponse:
    """Seed demo wardrobe items for the current user.

    Only adds items if the user's wardrobe is empty.
    Safe to call multiple times — idempotent.
    """
    user_id = current_user.id
    existing = db.query(Wardrobe).filter(Wardrobe.user_id == user_id).count()
    if existing > 0:
        return {
            "status": "success",
            "data": {"count": existing},
            "message": f"Already have {existing} items in wardrobe.",
        }

    for item_data in _DEMO_WARDROBE_ITEMS:
        item = Wardrobe(user_id=user_id, **item_data)
        db.add(item)
    db.commit()

    logger.info("POST /stylist/seed-demo — user_id=%d seeded %d items", user_id, len(_DEMO_WARDROBE_ITEMS))
    return {
        "status": "success",
        "data": {"count": len(_DEMO_WARDROBE_ITEMS)},
        "message": f"Seeded {len(_DEMO_WARDROBE_ITEMS)} demo wardrobe items.",
    }


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

    # ── No wardrobe — try real AI only ────────────────────
    if not items:
        logger.info(
            "[WUTT] source=init endpoint=/recommend user_id=%d no_wardrobe",
            user_id,
        )

        # Try Gemini/OpenAI for general fashion advice (no wardrobe context)
        _ai_kwargs: dict[str, Any] = dict(
            wardrobe_items=[],
            occasion=body.occasion,
            weather_desc=None,
            temperature_c=None,
            humidity=None,
            height_cm=profile.height_cm if profile else None,
            skin_tone=profile.skin_tone if profile else None,
            style_preference=profile.style_preference if profile else None,
        )

        source = "api_error"
        ai_result: dict[str, Any] | None = None

        # 1. Try OpenAI first
        if settings.openai_api_key:
            try:
                ai_result = openai_recommend(**_ai_kwargs)
                if ai_result is not None:
                    source = "openai"
                    logger.info("[WUTT] source=openai endpoint=/recommend no_wardrobe=True")
            except Exception as exc:
                logger.warning("[WUTT] source=api_error endpoint=/recommend openai_error=%s", type(exc).__qualname__)

        # 2. Try Gemini
        if ai_result is None and settings.gemini_api_key:
            try:
                ai_result = gemini_recommend(**_ai_kwargs)
                if ai_result is not None:
                    source = "gemini"
                    logger.info("[WUTT] source=gemini endpoint=/recommend no_wardrobe=True")
            except Exception as exc:
                logger.warning("[WUTT] source=api_error endpoint=/recommend gemini_error=%s", type(exc).__qualname__)

        # 3. No AI available — return error
        if ai_result is None:
            source = "api_error"
            logger.info("[WUTT] source=api_error endpoint=/recommend reason=no_ai_no_wardrobe")
            ai_result = {
                "outfit": [],
                "explanation": (
                    "Real AI styling is currently unavailable. "
                    "Please check API key or quota. Try again later."
                ),
                "weather_based_tip": "",
            }

        outfit, explanation, weather_based_tip = _extract_outfit_fields(ai_result)

        # Save session for history
        session = StyleSession(
            user_id=user_id,
            occasion=body.occasion,
            weather_desc=None,
            temperature_c=None,
            location=None,
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
                "weather_desc": None,
                "temperature_c": None,
                "location": None,
                "outfit": outfit,
                "explanation": explanation,
                "weather_based_tip": weather_based_tip,
                "created_at": _isoformat(session.created_at),
                "source": source,
            },
            "message": (
                "General fashion advice — upload wardrobe items for personalised recommendations."
            ),
        }

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
            "subtype": item.subtype,
            "color": item.color,
            "description": item.description,
            "style_tags": item.style_tags,
            "occasion_tags": item.occasion_tags,
        })

    # ── Call real AI only — OpenAI → Gemini → error ──────
    source: str = "api_error"
    ai_result: dict[str, Any] | None = None

    logger.info(
        "[WUTT] source=init endpoint=/recommend user_id=%d openai_key=%s gemini_key=%s",
        user_id, bool(settings.openai_api_key), bool(settings.gemini_api_key),
    )

    # Shared kwargs for all AI calls
    _ai_kwargs: dict[str, Any] = dict(
        wardrobe_items=wardrobe_images,
        occasion=body.occasion,
        weather_desc=weather_desc,
        temperature_c=temperature_c,
        humidity=humidity,
        height_cm=profile.height_cm if profile else None,
        skin_tone=profile.skin_tone if profile else None,
        style_preference=profile.style_preference if profile else None,
    )

    # 1. Try OpenAI first
    if settings.openai_api_key:
        try:
            ai_result = openai_recommend(**_ai_kwargs)
            if ai_result is not None:
                source = "openai"
                logger.info("[WUTT] source=openai endpoint=/recommend items=%d", len(ai_result.get("outfit", [])))
            else:
                logger.info("[WUTT] source=openai endpoint=/recommend result=None → trying Gemini")
        except Exception as exc:
            cls = type(exc).__qualname__
            mod = type(exc).__module__
            logger.warning("[WUTT] source=api_error endpoint=/recommend openai_error=%s.%s", mod, cls)

    # 2. Try Gemini if OpenAI didn't return a result
    if ai_result is None and settings.gemini_api_key:
        try:
            ai_result = gemini_recommend(**_ai_kwargs)
            if ai_result is not None:
                source = "gemini"
                logger.info("[WUTT] source=gemini endpoint=/recommend items=%d", len(ai_result.get("outfit", [])))
            else:
                logger.info("[WUTT] source=gemini endpoint=/recommend result=None")
        except Exception as exc:
            cls = type(exc).__qualname__
            mod = type(exc).__module__
            logger.warning("[WUTT] source=api_error endpoint=/recommend gemini_error=%s.%s", mod, cls)

    # 3. No AI available — return error, no fallback
    if ai_result is None:
        source = "api_error"
        logger.info("[WUTT] source=api_error endpoint=/recommend reason=no_ai_response")
        ai_result = {
            "outfit": [],
            "explanation": (
                "Real AI styling is currently unavailable. "
                "Please check API key or quota. Try again later."
            ),
            "weather_based_tip": "",
        }

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

    logger.info("[WUTT] source=%s endpoint=/recommend user_id=%d", source, user_id)

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
            f"Recommendation generated successfully (source: {source})."
        ),
    }


@router.post("/chat")
def chat_with_stylist(
    body: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuthResponse:
    """General chat with the AI stylist.

    Handles greetings, fashion questions, WUTT explanations, and casual chat.
    For specific outfit requests, use /stylist/recommend instead.
    """
    user_id = current_user.id
    message = body.message.strip()

    logger.info(
        "POST /stylist/chat — user_id=%d message_length=%d",
        user_id, len(message),
    )

    # Fetch user context
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    items = (
        db.query(Wardrobe)
        .filter(Wardrobe.user_id == user_id)
        .all()
    )

    # Build wardrobe context for Gemini
    wardrobe_context: list[dict[str, Any]] = []
    for item in items[:15]:  # Limit to 15 items for context
        wardrobe_context.append({
            "category": item.category,
            "color": item.color,
            "description": item.description,
        })

    # Detect if user is asking about WUTT / app usage
    msg_lower = message.lower()
    is_app_question = any(w in msg_lower for w in (
        "wutt", "how to", "how do", "upload", "wardrobe", "save", "delete",
        "what is", "app", "ဘာလဲ", "ဘယ်လိုသုံး",
    ))
    is_fashion_question = any(w in msg_lower for w in (
        "wear", "outfit", "style", "fashion", "color", "colour", "match",
        "trend", "season", "wedding", "date", "casual", "formal",
        "ဝတ်", "ဖို့", "ပွဲ", "လောင်း",
    ))

    # Build knowledge context string
    knowledge_context = ""
    if is_app_question and APP_GUIDE:
        knowledge_context += (
            "\n\n[App Guide — use this to answer how-to questions]\n"
            + json.dumps(APP_GUIDE, indent=2, ensure_ascii=False)[:2000]
        )
    if is_fashion_question and FASHION_KNOWLEDGE:
        # Include relevant sections
        sections = {}
        for key in ("color_matching_rules", "trend_colors_2026", "myanmar_climate_style"):
            if key in FASHION_KNOWLEDGE:
                sections[key] = FASHION_KNOWLEDGE[key]
        if sections:
            knowledge_context += (
                "\n\n[Fashion Knowledge]\n"
                + json.dumps(sections, indent=2, ensure_ascii=False)[:2000]
            )

    # ── Call real AI only — no fake fallback ──────────────
    source = "api_error"
    response_text: str | None = None
    last_error: str = ""

    # Build enriched message once (shared across providers)
    enriched_message = message
    if knowledge_context:
        enriched_message = message + knowledge_context

    # 1. Try OpenRouter (primary)
    if settings.openrouter_api_key:
        try:
            response_text = openrouter_chat(
                user_message=enriched_message,
                conversation_history=body.conversation_history,
                wardrobe_items=wardrobe_context if wardrobe_context else None,
            )
            if response_text:
                source = "openrouter"
                logger.info("[WUTT] source=openrouter endpoint=/chat chars=%d", len(response_text))
        except Exception as exc:
            last_error = str(exc)
            cls = type(exc).__qualname__
            mod = type(exc).__module__
            logger.warning("[WUTT] source=api_error endpoint=/chat openrouter_error=%s.%s", mod, cls)

    # 2. Fallback to Gemini if OpenRouter failed
    if not response_text and settings.gemini_api_key:
        try:
            response_text = get_chat_response(
                user_message=enriched_message,
                conversation_history=body.conversation_history,
                wardrobe_items=wardrobe_context if wardrobe_context else None,
            )
            if response_text:
                source = "gemini"
                logger.info("[WUTT] source=gemini endpoint=/chat chars=%d", len(response_text))
        except Exception as exc:
            last_error = str(exc)
            cls = type(exc).__qualname__
            mod = type(exc).__module__
            logger.warning("[WUTT] source=api_error endpoint=/chat gemini_error=%s.%s", mod, cls)

    # 3. Fallback to OpenAI if Gemini also failed
    if not response_text and settings.openai_api_key:
        try:
            response_text = openai_chat(
                user_message=enriched_message,
                conversation_history=body.conversation_history,
                wardrobe_items=wardrobe_context if wardrobe_context else None,
            )
            if response_text:
                source = "openai"
                logger.info("[WUTT] source=openai endpoint=/chat chars=%d", len(response_text))
        except Exception as exc:
            cls = type(exc).__qualname__
            mod = type(exc).__module__
            logger.warning("[WUTT] source=api_error endpoint=/chat openai_error=%s.%s", mod, cls)

    # 4. No AI available — return clear error
    if not response_text:
        if not settings.openrouter_api_key and not settings.gemini_api_key and not settings.openai_api_key:
            source = "api_error"
            logger.info("[WUTT] source=api_error endpoint=/chat reason=no_api_key")
        else:
            source = "api_error"
            logger.info("[WUTT] source=api_error endpoint=/chat reason=all_providers_failed")
        response_text = (
            "Real AI styling is currently unavailable. "
            "Please check API key or quota. Try again later."
        )

    # Save to session history
    session = StyleSession(
        user_id=user_id,
        occasion="chat",
        weather_desc=None,
        temperature_c=None,
        location=None,
        ai_response=json.dumps({
            "message": message,
            "response": response_text,
            "source": source,
        }, ensure_ascii=False),
    )
    db.add(session)
    db.commit()

    logger.info("[WUTT] source=%s endpoint=/chat user_id=%d", source, user_id)

    return {
        "status": "success",
        "data": {
            "response": response_text,
            "source": source,
        },
        "message": "Chat response generated.",
    }


@router.post("/analyze")
def analyze_clothing(
    body: AnalyzeRequest,
    current_user: User = Depends(get_current_user),
) -> AuthResponse:
    """Analyze a clothing image using Gemini Vision.

    Sends the image to Gemini for analysis: category, color, fit, style,
    material guess, occasion tags, and matching ideas.

    Returns the analysis for the user to review and edit before saving.
    """
    user_id = current_user.id

    logger.info(
        "[WUTT] source=init endpoint=/analyze user_id=%d mime=%s",
        user_id, body.mime_type,
    )

    if not settings.gemini_api_key:
        logger.info("[WUTT] source=api_error endpoint=/analyze reason=no_api_key")
        return {
            "status": "error",
            "data": {},
            "message": "Real AI styling is currently unavailable. Please check API key or quota.",
        }

    # Strip data URI prefix if present
    image_data = body.image_data
    if "," in image_data and image_data.startswith("data:"):
        image_data = image_data.split(",", 1)[1]

    analysis = analyze_clothing_image(
        image_data=image_data,
        mime_type=body.mime_type,
    )

    if analysis is None:
        logger.info("[WUTT] source=api_error endpoint=/analyze reason=vision_failed user_id=%d", user_id)
        return {
            "status": "error",
            "data": {},
            "message": "Real AI styling is currently unavailable. Please check API key or quota.",
        }

    logger.info(
        "[WUTT] source=gemini endpoint=/analyze user_id=%d category=%s color=%s confidence=%d",
        user_id, analysis.get("category"), analysis.get("color"), analysis.get("confidence", 0),
    )

    return {
        "status": "success",
        "data": analysis,
        "message": "Clothing analysis complete.",
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
