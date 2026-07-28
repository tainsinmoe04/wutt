"""Stylist routes: get outfit recommendations, chat, and view history.

Endpoints
    POST /stylist/recommend        —  AI-powered outfit recommendation.
    POST /stylist/chat             —  General chat with AI stylist.
    GET  /stylist/history/{user_id} —  List past style sessions.
    DELETE /stylist/history/{user_id}/today — Delete only today's sessions.

Requires authentication on all endpoints.
"""

import json
import logging
import random
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models import User, Profile, Wardrobe, StyleSession
from routes.auth import get_current_user
from services.weather_svc import get_current_weather, WeatherData
from services.openai_svc import get_outfit_recommendation as openai_recommend
from services.gemini_svc import get_outfit_recommendation as gemini_recommend
from services.gemini_svc import get_chat_response
from services.openai_svc import get_chat_response as openai_chat
from services.openrouter_svc import (
    get_chat_response as openrouter_chat,
    get_outfit_recommendation as openrouter_recommend,
)
from services.stylist_prompt import (
    accessory_selection_type,
    classify_occasion_context,
    is_body_fit_request,
    is_luxury_style_request,
    is_shopping_intent,
    is_visual_comparison_request,
    normalize_stylist_query,
)
from services.gemini_svc import analyze_clothing_image
from services.gemini_svc import FASHION_KNOWLEDGE, APP_GUIDE
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Pydantic Schemas ───────────────────────────────────


class RecommendRequest(BaseModel):
    """Payload for POST /stylist/recommend."""

    occasion: str = Field(
        ..., min_length=1, max_length=1000,
        description="Occasion or natural-language styling request.",
    )

    @field_validator("occasion", mode="before")
    @classmethod
    def normalize_occasion(cls, value):
        """Accept natural questions while normalizing accidental whitespace."""
        return normalize_stylist_query(value)


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


def _session_occasion(query: str) -> str:
    """Fit a natural-language request into the legacy 100-character session label."""
    if len(query) <= 100:
        return query
    shortened = query[:97].rsplit(" ", 1)[0].rstrip()
    return (shortened or query[:97]).rstrip() + "..."


def _recommendation_query_with_recent_context(
    query: str,
    recent_sessions: list[StyleSession],
) -> str:
    """Carry an occasion only when the current request is a vague style follow-up."""
    normalized = normalize_stylist_query(query).casefold()

    # The current request always wins. Shopping, an explicit occasion, a named
    # garment, and body/fit advice are complete requests rather than continuations.
    if is_shopping_intent(query):
        return query

    named_garment_terms = (
        "dress", "gown", "shirt", "blouse", "top", "skirt", "trousers",
        "pants", "jeans", "shorts", "jacket", "blazer", "coat", "suit",
        "longyi", "htamein", "shoe", "shoes", "heels", "sneakers", "bag",
        "watch", "jewelry", "jewellery", "အင်္ကျီ", "ဂါဝန်", "စကတ်",
        "ဘောင်းဘီ", "ဖိနပ်", "အိတ်", "နာရီ", "လုံချည်", "ထမီ",
    )
    new_event_terms = (
        "event", "gala", "ceremony", "conference", "presentation",
        "graduation", "funeral", "concert", "festival", "prom",
        "tomorrow", "tonight", "this evening", "this weekend",
        "ပွဲ", "မနက်ဖြန်", "ဒီည",
    )
    vague_followup_terms = (
        "version", "more ", "make it", "better", "upgrade", "elevate",
        "instead", "another", "same", "ပိုပြီး", "နောက်တစ်",
        "ပုံစံပြောင်း",
    )

    if (
        classify_occasion_context(query) != "general"
        or any(term in normalized for term in named_garment_terms)
        or is_body_fit_request(query)
        or any(term in normalized for term in new_event_terms)
        or not any(term in normalized for term in vague_followup_terms)
    ):
        return query
    for session in recent_sessions:
        created_at = session.created_at
        if created_at and created_at.date() != datetime.now(timezone.utc).date():
            continue
        previous = str(session.occasion or "").strip()
        if previous.casefold() == "chat":
            continue
        if classify_occasion_context(previous) != "general":
            return f"{previous}. Requested style: {query}"
    return query


def _extract_outfit_fields(ai_result: dict[str, Any]) -> tuple[list[str], str, str]:
    """Safely extract outfit, explanation, and weather_based_tip from AI result."""
    if not ai_result:
        return [], "", ""
    return (
        ai_result.get("outfit") or [],
        ai_result.get("explanation") or "",
        ai_result.get("weather_based_tip") or "",
    )


def _wardrobe_display_name(item: dict[str, Any]) -> str:
    """Return a clean user-facing label from saved wardrobe metadata."""
    raw = (
        item.get("subtype")
        or item.get("description")
        or item.get("category")
        or "Wardrobe Item"
    )
    cleaned = re.sub(
        r"(?i)(?:\s*[-–—|,/]\s*)?\b(?:cute\s*(?:and|&)\s*sexy|cute|sexy|"
        r"playful|casual|everyday)\b",
        "",
        str(raw),
    )
    cleaned = re.sub(r"\s*[-–—|,/]\s*$", "", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    words = (cleaned or str(item.get("category") or "Wardrobe Item")).split()
    return " ".join(
        word if not re.search(r"[A-Za-z]", word) else word[:1].upper() + word[1:].lower()
        for word in words
    )


def _wardrobe_identity(item: dict[str, Any]) -> str:
    """Return an unambiguous saved-item label for recommendation output."""
    name = _wardrobe_display_name(item)
    category = str(item.get("category") or "Item").strip()
    color = str(item.get("color") or "Unspecified color").strip()
    item_id = item.get("id")
    identity = f"{name} — {category}, {color}"
    return f"{identity} (id {item_id})" if item_id is not None else identity


def _contains_term(text: str, term: str) -> bool:
    """Return whether *term* appears as a phrase or word in normalized text."""
    normalized_term = term.casefold().strip()
    if not normalized_term:
        return False
    return bool(re.search(
        rf"(?<!\w){re.escape(normalized_term)}(?!\w)",
        text.casefold(),
    ))


def _explicit_item_match_score(query: str, item: dict[str, Any]) -> int:
    """Score only evidence that the user explicitly named a saved item."""
    score = 0
    subtype = str(item.get("subtype") or "").strip()
    category = str(item.get("category") or "").strip()
    color = str(item.get("color") or "").strip()
    description = str(item.get("description") or "").strip()
    item_id = item.get("id")
    if item_id is not None and re.search(rf"(?i)\b(?:id\s*=?\s*|#){item_id}\b", query):
        score += 200
    if subtype and _contains_term(query, subtype):
        score += 120
    if description and len(description) >= 8 and _contains_term(query, description):
        score += 90
    color_match = bool(color and _contains_term(query, color))
    category_match = bool(category and _contains_term(query, category))
    if color_match:
        score += 35
    if category_match:
        score += 30
    subtype_tokens = {
        token for token in re.findall(r"[\w\u1000-\u109f]+", subtype.casefold())
        if len(token) >= 3
    }
    score += min(
        sum(12 for token in subtype_tokens if _contains_term(query, token)),
        36,
    )
    if color_match and (category_match or any(
        _contains_term(query, token) for token in subtype_tokens
    )):
        score += 60
    return score


def _wardrobe_relevance_score(
    item: dict[str, Any],
    query: str,
    profile: Profile | None,
) -> int:
    """Rank wardrobe context by explicit mention, occasion, style, and profile."""
    explicit_score = _explicit_item_match_score(query, item)
    normalized_query = query.casefold()
    occasion = classify_occasion_context(query)
    occasion_terms = {
        occasion,
        "religious" if occasion == "religious_place" else "",
        "work" if occasion == "business_meeting" else "",
        "formal" if occasion in {"party", "dinner", "business_meeting"} else "",
    }
    occasion_tags = str(item.get("occasion_tags") or "").casefold()
    style_tags = str(item.get("style_tags") or "").casefold()
    color = str(item.get("color") or "").casefold()
    score = explicit_score * 10
    if any(term and term in occasion_tags for term in occasion_terms):
        score += 80
    item_metadata = " ".join(
        str(item.get(field) or "").casefold()
        for field in (
            "category", "subtype", "description", "style_tags",
            "occasion_tags", "formality_level",
        )
    )
    if occasion in {"party", "dinner"}:
        if any(term in item_metadata for term in (
            "dress", "gown", "traditional", "myanmar", "longyi", "htamein",
            "elegant", "formal", "refined", "skirt", "heel", "structured",
            "jewelry", "jewellery", "watch", "မြန်မာ", "ရိုးရာ", "လုံချည်",
        )):
            score += 70
        if any(term in item_metadata for term in (
            "jeans", "denim", "hoodie", "streetwear", "sportswear",
            "sneaker", "everyday", "basic", "casual",
        )):
            score -= 90
    if is_luxury_style_request(query):
        if any(term in item_metadata for term in (
            "dress", "silk", "traditional", "myanmar", "longyi", "htamein",
            "blazer", "tailored", "trouser", "skirt", "heel", "leather shoe",
            "structured", "fine", "jewelry", "jewellery", "watch",
            "luxury", "elegant", "premium", "classy", "old money",
        )):
            score += 75
        if any(term in item_metadata for term in (
            "jeans", "denim", "hoodie", "basic", "casual", "streetwear",
        )):
            score -= 100
    query_tokens = {
        token for token in re.findall(r"[\w\u1000-\u109f]+", normalized_query)
        if len(token) >= 3
    }
    score += min(sum(8 for token in query_tokens if token in style_tags), 32)
    color_sets = {
        "wedding": _WEDDING_COLORS,
        "business_meeting": _INTERVIEW_COLORS,
        "work": _INTERVIEW_COLORS,
    }
    if color and color in color_sets.get(occasion, set()):
        score += 18
    if profile and profile.style_preference:
        profile_styles = {
            value.strip().casefold()
            for value in profile.style_preference.split(",")
            if value.strip()
        }
        score += min(sum(6 for value in profile_styles if value in style_tags), 18)
    score -= min(int(item.get("recent_recommendation_count") or 0) * 5, 15)
    return score


def _rank_wardrobe_context(
    wardrobe_items: list[dict[str, Any]],
    query: str,
    profile: Profile | None,
) -> list[dict[str, Any]]:
    """Return wardrobe items in retrieval priority order without dropping any."""
    return sorted(
        wardrobe_items,
        key=lambda item: _wardrobe_relevance_score(item, query, profile),
        reverse=True,
    )


def _find_explicit_anchor(
    query: str,
    wardrobe_items: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Resolve an explicitly mentioned garment to one exact saved record."""
    ranked = sorted(
        wardrobe_items,
        key=lambda item: _explicit_item_match_score(query, item),
        reverse=True,
    )
    if not ranked or _explicit_item_match_score(query, ranked[0]) < 60:
        return None
    return ranked[0]


def _query_mentions_clothing(query: str) -> bool:
    """Return whether text already names a garment, accessory, color, or wardrobe id."""
    normalized = query.casefold()
    if re.search(r"(?i)\b(?:id\s*=?\s*|#)\d+\b", query):
        return True
    terms = (
        "top", "shirt", "blouse", "dress", "skirt", "trouser", "pants",
        "jeans", "longyi", "jacket", "blazer", "watch", "bag", "shoe",
        "sandal", "accessory", "အင်္ကျီ", "ဂါဝန်", "စကတ်", "ဘောင်းဘီ",
        "လုံချည်", "နာရီ", "အိတ်", "ဖိနပ်",
    )
    colors = (
        "black", "white", "brown", "navy", "purple", "red", "green",
        "blue", "beige", "cream", "gold", "silver", "အနက်", "အဖြူ",
        "အညို", "ခရမ်း", "အနီ", "အစိမ်း",
    )
    return any(term in normalized for term in terms + colors)


def _match_outfit_item(
    text: str,
    wardrobe_items: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Match provider wording back to the closest ranked wardrobe record."""
    for item in wardrobe_items:
        item_id = item.get("id")
        if item_id is not None and re.search(
            rf"(?i)\b(?:id\s*=?\s*|#){item_id}\b",
            text,
        ):
            return item
    scored = [
        (_explicit_item_match_score(text, item), item)
        for item in wardrobe_items
    ]
    scored.sort(key=lambda entry: entry[0], reverse=True)
    return scored[0][1] if scored and scored[0][0] >= 25 else None


def _normalize_outfit_labels(
    outfit: list[Any],
    wardrobe_items: list[dict[str, Any]],
) -> list[str]:
    """Ground provider wording to unambiguous saved wardrobe identities."""
    normalized: list[str] = []
    for raw_item in outfit:
        text = str(raw_item).strip()
        matched_item = _match_outfit_item(text, wardrobe_items)
        if matched_item:
            label = _wardrobe_identity(matched_item)
        else:
            label = text.strip(" -–—,;")
        label = re.sub(r"(?i)^suggested:\s*", "", label).strip()
        if label and label not in normalized:
            normalized.append(label)
    return normalized


def _refine_marketing_tag_language(text: str, query: str) -> str:
    """Turn unwanted wardrobe marketing tags into natural stylist language."""
    if not text:
        return ""
    requested = query.casefold()
    copy = text
    if not any(term in requested for term in ("cute", "ချစ်စရာ")):
        copy = re.sub(r"(?i)\bcute\b", "polished", copy)
    if not any(term in requested for term in ("sexy", "ဆက်ဆီ")):
        copy = re.sub(r"(?i)\bsexy\b", "confident", copy)
    if not any(term in requested for term in ("playful",)):
        copy = re.sub(r"(?i)\bplayful\b", "expressive", copy)
    if not any(term in requested for term in ("casual", "coffee", "everyday")):
        copy = re.sub(r"(?i)\b(?:casual|everyday)\b", "refined", copy)
    return re.sub(r"\s{2,}", " ", copy).strip()


def _executive_outfit_conflicts(
    outfit: list[Any],
    wardrobe_items: list[dict[str, Any]],
    query: str,
) -> bool:
    """Reject provider choices whose saved metadata contradicts executive intent."""
    if not is_luxury_style_request(query):
        return False
    conflicting_terms = (
        "cute", "sexy", "playful", "casual", "everyday", "streetwear",
        "jeans", "denim", "hoodie", "basic",
    )
    for raw_item in outfit:
        matched = _match_outfit_item(str(raw_item), wardrobe_items)
        if not matched:
            continue
        metadata = " ".join(
            str(matched.get(field) or "").casefold()
            for field in (
                "category", "subtype", "description", "style_tags",
                "occasion_tags",
            )
        )
        if any(term in metadata for term in conflicting_terms):
            return True
    return False


def _personalize_explanation(
    explanation: str,
    outfit: list[str],
    wardrobe_items: list[dict[str, Any]],
) -> str:
    """Keep the provider's specific reasoning without adding repetitive filler."""
    return explanation.strip()


def _preserve_requested_base(
    outfit: list[str],
    query: str,
    wardrobe_items: list[dict[str, Any]],
) -> list[str]:
    """Keep one exact user-mentioned wardrobe record as the first outfit item."""
    anchor = _find_explicit_anchor(query, wardrobe_items)
    if anchor is None:
        return outfit

    base_label = _wardrobe_identity(anchor)
    match_terms = [
        value.casefold()
        for value in (
            base_label,
            _wardrobe_display_name(anchor),
            str(anchor.get("subtype") or "").strip(),
        )
        if value
    ]
    remaining = [
        item for item in outfit
        if not any(term in item.casefold() for term in match_terms)
    ]
    anchor_type = _classify_item(anchor)
    conflicting_terms = {
        "top": (" top", "shirt", "blouse", "tee", "sweater", "hoodie"),
        "bottom": (" bottom", "skirt", "trouser", "pants", "jeans", "longyi"),
        "dress": (" dress", "gown", "jumpsuit"),
        "traditional": ("traditional set", "myanmar outfit"),
    }.get(anchor_type, ())
    remaining = [
        item for item in remaining
        if not any(term in f" {item.casefold()}" for term in conflicting_terms)
    ]
    return [base_label] + remaining


def _remove_technical_ids(
    text: str,
    wardrobe_items: list[dict[str, Any]],
) -> str:
    """Remove provider-facing IDs from friendly explanation copy."""
    cleaned = str(text or "")
    labels_by_id = {
        int(item["id"]): _wardrobe_display_name(item)
        for item in wardrobe_items
        if item.get("id") is not None
    }
    for item_id, label in labels_by_id.items():
        cleaned = re.sub(
            rf"(?i)\s*[\[(]\s*(?:id\s*=?\s*|#){item_id}\s*[\])]",
            "",
            cleaned,
        )
        cleaned = re.sub(
            rf"(?i)\b(?:id\s*=?\s*|#){item_id}\b",
            label,
            cleaned,
        )
    cleaned = re.sub(r"(?i)\s*[\[(]?\s*(?:id\s*=?\s*|#)\d+\s*[\])]?", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _remove_unowned_possessives(
    text: str,
    wardrobe_items: list[dict[str, Any]],
) -> str:
    """Prevent possessive wording for generic items absent from the wardrobe."""
    inventory = " ".join(
        str(item.get(field) or "").casefold()
        for item in wardrobe_items
        for field in ("category", "subtype", "material_tags", "description")
    )
    cleaned = str(text or "")
    replacements = {
        "watch": "a watch",
        "bag": "a bag",
        "shoes": "shoes",
        "shoe": "a shoe",
        "linen": "a linen piece",
    }
    for noun, replacement in replacements.items():
        if noun not in inventory:
            cleaned = re.sub(
                rf"(?i)\byour\s+{re.escape(noun)}\b",
                replacement,
                cleaned,
            )
    return cleaned


def _complete_outfit_presentation(outfit: list[str], query: str) -> list[str]:
    """Add clean finishing-piece labels when a provider omits them."""
    if not outfit:
        return outfit
    combined = " ".join(outfit).casefold()
    context = classify_occasion_context(query)
    keyword_groups = {
        "shoes": ("shoe", "sandal", "heel", "loafer", "sneaker", "ဖိနပ်"),
        "bag": ("bag", "clutch", "tote", "handbag", "အိတ်"),
        "accessory": (
            "accessory", "jewelry", "jewellery", "earring", "necklace",
            "watch", "bracelet", "belt", "နာရီ", "လက်ဝတ်",
        ),
        "layer": (
            "layer", "jacket", "cardigan", "shawl", "blazer", "coat",
            "outerwear", "အပေါ်ထပ်",
        ),
    }
    suggestions = {
        "religious_place": {
            "shoes": "Suggested: Easy-to-remove sandals",
            "bag": "Suggested: Small, secure shoulder bag",
            "accessory": "Suggested: Simple watch or understated jewelry",
            "layer": "Suggested: Light shawl for extra coverage",
        },
        "wedding": {
            "shoes": "Suggested: Polished dress shoes or elegant sandals",
            "bag": "Suggested: Small clutch or structured bag",
            "accessory": "Suggested: One refined jewelry detail",
            "layer": "Suggested: Light shawl or tailored layer",
        },
        "party": {
            "shoes": "Suggested: Elegant heels or polished shoes",
            "bag": "Suggested: Small structured bag or clutch",
            "accessory": "Suggested: Refined jewelry or a watch",
            "layer": "Suggested: Tailored evening layer",
        },
        "dinner": {
            "shoes": "Suggested: Elegant heels or polished shoes",
            "bag": "Suggested: Small structured bag",
            "accessory": "Suggested: Refined jewelry or a watch",
            "layer": "Suggested: Light polished layer",
        },
        "luxury": {
            "shoes": "Suggested: Elegant heels or polished leather shoes",
            "bag": "Suggested: Structured bag",
            "accessory": "Suggested: Fine jewelry or a minimal watch",
            "layer": "Suggested: Tailored blazer",
        },
        "fit": {
            "shoes": "Suggested: Pointed comfortable shoes",
            "bag": "Suggested: Small structured bag",
            "accessory": "Suggested: One minimal vertical-detail accessory",
            "layer": "Suggested: Short tailored jacket",
        },
        "date": {
            "shoes": "Suggested: Clean, comfortable shoes",
            "bag": "Suggested: Small shoulder bag",
            "accessory": "Suggested: One simple personal accessory",
            "layer": "Suggested: Light layer for later",
        },
        "travel": {
            "shoes": "Suggested: Comfortable walking shoes",
            "bag": "Suggested: Secure crossbody bag",
            "accessory": "Suggested: Sunglasses or a simple watch",
            "layer": "Suggested: Packable light layer",
        },
        "business_meeting": {
            "shoes": "Suggested: Clean, polished shoes",
            "bag": "Suggested: Structured work bag",
            "accessory": "Suggested: Minimal watch",
            "layer": "Suggested: Tailored blazer",
        },
    }
    default = {
        "shoes": "Suggested: Clean, comfortable shoes",
        "bag": "Suggested: Simple everyday bag",
        "accessory": "Suggested: One understated accessory",
        "layer": "Suggested: Light optional layer",
    }
    suggestion_context = (
        "luxury"
        if context == "general" and is_luxury_style_request(query)
        else ("fit" if context == "general" and is_body_fit_request(query) else context)
    )
    context_suggestions = suggestions.get(suggestion_context, default)
    completed = list(outfit)
    for slot, keywords in keyword_groups.items():
        if not any(keyword in combined for keyword in keywords):
            completed.append(context_suggestions[slot])
    return _normalize_outfit_labels(completed, [])


def _context_only_outfit(
    query: str,
    profile: Profile | None,
) -> dict[str, Any]:
    """Return an immediate suggested look when no saved wardrobe is available."""
    context = classify_occasion_context(query)
    look_context = (
        "luxury"
        if context == "general" and is_luxury_style_request(query)
        else ("fit" if context == "general" and is_body_fit_request(query) else context)
    )
    looks = {
        "religious_place": [
            "Suggested: Modest Myanmar blouse",
            "Suggested: Longyi or htamein",
            "Suggested: Easy-to-remove sandals",
            "Suggested: Small, secure shoulder bag",
            "Suggested: Simple watch or understated jewelry",
            "Suggested: Light shawl for extra coverage",
        ],
        "wedding": [
            "Suggested: Refined Myanmar traditional outfit",
            "Suggested: Polished dress shoes or elegant sandals",
            "Suggested: Small clutch or structured bag",
            "Suggested: One refined jewelry detail",
            "Suggested: Light shawl or tailored layer",
        ],
        "party": [
            "Suggested: Elegant dress or refined Myanmar traditional outfit",
            "Suggested: Elegant heels or polished shoes",
            "Suggested: Small structured bag or clutch",
            "Suggested: Refined jewelry or a watch",
            "Suggested: Tailored evening layer",
        ],
        "date": [
            "Suggested: Clean top with a softly polished skirt or trousers",
            "Suggested: Clean, comfortable shoes",
            "Suggested: Small shoulder bag",
            "Suggested: One simple personal accessory",
            "Suggested: Light layer for later",
        ],
        "dinner": [
            "Suggested: Elegant dress, refined traditional outfit, or polished skirt and top",
            "Suggested: Elegant heels or polished shoes",
            "Suggested: Small structured bag",
            "Suggested: Refined jewelry or a watch",
            "Suggested: Light polished layer",
        ],
        "luxury": [
            "Suggested: Elegant dress or tailored shirt with refined trousers",
            "Suggested: Elegant heels or polished leather shoes",
            "Suggested: Structured bag",
            "Suggested: Fine jewelry or a minimal watch",
            "Suggested: Tailored blazer",
        ],
        "fit": [
            "Suggested: High-waisted tailored trousers or skirt",
            "Suggested: Clean fitted or tucked top",
            "Suggested: Pointed comfortable shoes",
            "Suggested: Small structured bag",
            "Suggested: Short tailored jacket",
        ],
        "work": [
            "Suggested: Clean shirt or blouse with tailored trousers",
            "Suggested: Comfortable closed-toe shoes",
            "Suggested: Structured everyday bag",
            "Suggested: Simple watch",
            "Suggested: Light blazer or cardigan",
        ],
        "travel": [
            "Suggested: Breathable top with comfortable trousers",
            "Suggested: Comfortable walking shoes",
            "Suggested: Secure crossbody bag",
            "Suggested: Sunglasses or a simple watch",
            "Suggested: Packable light layer",
        ],
    }
    outfit = _normalize_outfit_labels(looks.get(look_context, [
        "Suggested: Easy top with comfortable trousers",
        "Suggested: Clean, comfortable shoes",
        "Suggested: Simple everyday bag",
        "Suggested: One understated accessory",
        "Suggested: Light optional layer",
    ]), [])
    if look_context == "luxury" and profile:
        gender = str(profile.gender or "").casefold()
        if gender in {"man", "male", "men", "ကျား"}:
            outfit = _normalize_outfit_labels([
                "Suggested: Tailored shirt",
                "Suggested: Tailored trousers",
                "Suggested: Blazer",
                "Suggested: Polished leather shoes",
                "Suggested: Minimal watch",
            ], [])
        elif gender in {"woman", "female", "women", "မ"}:
            outfit = _normalize_outfit_labels([
                "Suggested: Elegant dress, silk skirt look, or refined Myanmar traditional outfit",
                "Suggested: Elegant heels",
                "Suggested: Structured bag",
                "Suggested: Fine jewelry or a watch",
                "Suggested: Tailored blazer",
            ], [])
    style = (profile.style_preference or "").strip() if profile else ""
    personal_note = (
        f" Since you like {style}, keep the details in that style."
        if style else ""
    )
    explanations = {
        "religious_place": (
            "I’d go with a modest Myanmar look for the pagoda. A blouse with "
            "a longyi feels respectful, comfortable, and right for the setting."
        ),
        "wedding": (
            "I’d choose a refined traditional look for the wedding. It feels "
            "celebratory while still looking personal and polished."
        ),
        "date": (
            "I’d keep the date look clean and softly polished. The simple "
            "shape feels relaxed, and one personal accessory gives it character."
        ),
        "fit": (
            "I’d create one clean vertical line with a high waist and a neat tucked or fitted "
            "top. Balanced proportions matter more here than occasion or color matching."
        ),
    }
    explanation = explanations.get(
        look_context,
        "I’d keep this look clean, comfortable, and suited to the occasion.",
    ) + personal_note
    return {
        "outfit": outfit,
        "explanation": explanation,
        "weather_based_tip": (
            "Myanmar weather can feel hot and change quickly, so choose "
            "breathable fabric and keep the layer light."
        ),
    }


def _shopping_fallback(
    query: str,
    profile: Profile | None,
) -> dict[str, Any]:
    """Recommend useful purchases instead of forcing existing wardrobe pieces."""
    context = classify_occasion_context(query)
    luxury = is_luxury_style_request(query) or context in {
        "party", "dinner", "wedding", "business_meeting",
    }
    if luxury:
        purchases = [
            "Elegant midi or silk dress",
            "Premium Myanmar traditional outfit",
            "Structured blazer",
            "Heels or polished leather shoes",
            "Structured bag and one refined accessory",
        ]
        explanation = (
            "Start with the dress or premium traditional outfit, then add the blazer when you "
            "want a stronger executive finish. Those core pieces can create at least four looks "
            "across dinners, weddings, client events, and formal celebrations."
        )
    elif is_body_fit_request(query):
        purchases = [
            "High-waisted tailored trousers or skirt",
            "Clean fitted top for tucking in",
            "Short structured jacket",
            "Pointed comfortable shoes",
            "Simple vertical-detail accessory",
        ]
        explanation = (
            "These pieces keep the proportions balanced and create a longer vertical line. "
            "The top, bottom, and jacket can make at least six practical combinations."
        )
    else:
        purchases = [
            "Versatile clean top",
            "Well-fitting trousers or skirt",
            "Comfortable polished shoes",
            "Practical structured bag",
            "Light optional layer",
        ]
        explanation = (
            "Buy the top and bottom first because they can make at least four everyday outfits. "
            "The shoes, bag, and layer make the same pieces work across more settings."
        )
    style = str(profile.style_preference or "").strip() if profile else ""
    if style:
        explanation += f" Choose the details in your {style} preference."
    return {
        "outfit": purchases,
        "explanation": explanation,
        "weather_based_tip": (
            "Choose breathable fabric and test the full outfit for comfortable movement "
            "before buying."
        ),
    }


def _accessory_selection_fallback(
    wardrobe_items: list[dict[str, Any]],
    query: str,
) -> dict[str, Any]:
    """Choose only the requested finishing piece when providers are unavailable."""
    selection_type = accessory_selection_type(query)
    if not selection_type:
        return {}

    def matches(item: dict[str, Any]) -> bool:
        combined = " ".join(
            str(item.get(field) or "").casefold()
            for field in ("category", "subtype", "description")
        )
        if selection_type == "watch":
            return "watch" in combined or "နာရီ" in combined
        if selection_type == "bag":
            return "bag" in combined or "အိတ်" in combined
        if selection_type == "shoes":
            return _classify_item(item) == "shoes"
        return _classify_item(item) == "accessory"

    candidates = [item for item in wardrobe_items if matches(item)]
    candidates.sort(key=lambda item: int(item.get("recent_recommendation_count") or 0))
    visual_comparison = is_visual_comparison_request(query)
    if visual_comparison:
        metadata_fields = (
            "color", "description", "style_tags", "occasion_tags",
            "material_tags", "formality_level",
        )
        metadata_is_sufficient = (
            len(candidates) >= 2
            and all(
                sum(bool(str(item.get(field) or "").strip()) for field in metadata_fields) >= 2
                for item in candidates[:2]
            )
        )
        if not metadata_is_sufficient:
            return {
                "outfit": [],
                "explanation": (
                    "I can’t compare the photos yet. Image comparison will be available "
                    "with WUTT AI Vision in the future. Add color, style, and occasion "
                    "details for each option and I can compare their metadata."
                ),
                "weather_based_tip": "",
            }
    if not candidates:
        return {
            "outfit": [],
            "explanation": (
                f"I don’t see a saved {selection_type} to compare yet. Add one or two "
                "options and I’ll choose the best match."
            ),
            "weather_based_tip": "Keep the finish simple and consistent with the main outfit.",
        }

    selected = _wardrobe_identity(candidates[0])
    alternative = (
        _wardrobe_identity(candidates[1])
        if len(candidates) > 1
        else ""
    )
    explanation = f"I’d choose your {selected}. It gives the outfit a clean finish."
    if alternative:
        explanation += f" Alternative: {alternative}."
    if visual_comparison:
        explanation = (
            "I can’t compare the photos yet; WUTT AI Vision will support that in the "
            f"future. Based only on the saved metadata, {explanation}"
        )
    return {
        "outfit": [selected],
        "explanation": explanation,
        "weather_based_tip": "Keep the other accessories quieter so this choice feels intentional.",
    }


def _visual_comparison_fallback(
    wardrobe_items: list[dict[str, Any]],
    query: str,
) -> dict[str, Any]:
    """Return an honest non-vision response, using accessory metadata when possible."""
    if accessory_selection_type(query):
        return _accessory_selection_fallback(wardrobe_items, query)
    return {
        "outfit": [],
        "explanation": (
            "I can’t compare colors or clothing from photos yet. Image comparison will "
            "be available with WUTT AI Vision in the future. If you add the item names, "
            "colors, and style details, I can help using that metadata."
        ),
        "weather_based_tip": "",
    }


def _format_chat_recommendation(
    result: dict[str, Any],
) -> str:
    """Render a structured fallback as concise conversational chat text."""
    outfit = [str(item) for item in result.get("outfit") or [] if str(item).strip()]
    explanation = str(result.get("explanation") or "").strip()
    tip = str(result.get("weather_based_tip") or "").strip()
    sections: list[str] = []
    if outfit:
        sections.append("Recommended:\n" + "\n".join(f"- {item}" for item in outfit))
    if explanation:
        sections.append("Why:\n" + explanation)
    if tip:
        sections.append("Small tip:\n" + tip)
    return "\n\n".join(sections)


def _chat_wardrobe_fallback(
    message: str,
    wardrobe_items: list[dict[str, Any]],
    profile: Profile | None,
) -> str:
    """Continue from a matched item/context into a complete wardrobe recommendation."""
    ranked = _rank_wardrobe_context(wardrobe_items, message, profile)
    if accessory_selection_type(message):
        result = _accessory_selection_fallback(ranked, message)
    else:
        result = _wardrobe_fallback_outfit(ranked, message, None, profile)
        outfit = _normalize_outfit_labels(result.get("outfit") or [], ranked)
        outfit = _preserve_requested_base(outfit, message, ranked)
        result["outfit"] = _complete_outfit_presentation(outfit, message)
        result["explanation"] = _remove_unowned_possessives(
            _remove_technical_ids(result.get("explanation") or "", ranked),
            ranked,
        )
    return _format_chat_recommendation(result)


def _wardrobe_fallback_outfit(
    wardrobe_items: list[dict[str, Any]],
    query: str,
    temperature_c: float | None,
    profile: Profile | None,
) -> dict[str, Any]:
    """Build a complete immediate look with the existing rule-based wardrobe logic."""
    context = classify_occasion_context(query)
    luxury_style = is_luxury_style_request(query)
    body_fit_goal = is_body_fit_request(query)
    occasion_key = {
        "religious_place": "temple",
        "business_meeting": "interview",
        "wedding": "wedding",
        "date": "date",
        "casual_outing": "casual",
        "party": "party",
        "dinner": "party",
        "work": "work",
        "travel": "travel",
    }.get(
        context,
        "fit" if body_fit_goal else ("luxury" if luxury_style else "casual"),
    )
    classified: dict[str, list[dict[str, Any]]] = {
        key: [] for key in (
            "dress", "top", "bottom", "traditional", "outerwear",
            "accessory", "shoes", "unknown",
        )
    }
    scored: dict[str, list[tuple[int, dict[str, Any]]]] = {
        key: [] for key in classified
    }
    style_preference = profile.style_preference if profile else None
    normalized_query = query.casefold()
    allows_executive_conflict = any(term in normalized_query for term in (
        "cute", "sexy", "playful", "casual", "streetwear", "jeans", "hoodie",
    ))
    for item in wardrobe_items:
        item_metadata = " ".join(
            str(item.get(field) or "").casefold()
            for field in (
                "category", "subtype", "description", "style_tags",
                "occasion_tags",
            )
        )
        if context == "religious_place" and any(term in item_metadata for term in (
            "sexy", "mini", "revealing", "low-cut", "crop top", "party",
            "stiletto", "high heel", "ပေါ်လွင်", "တိုတို",
        )):
            continue
        if (
            luxury_style
            and not allows_executive_conflict
            and any(term in item_metadata for term in (
                "cute", "sexy", "playful", "casual", "everyday",
                "streetwear", "jeans", "denim", "hoodie", "basic",
            ))
        ):
            continue
        broad_type = _classify_item(item)
        classified[broad_type].append(item)
        item_score = _score_item(
            item,
            broad_type,
            occasion_key,
            temperature_c,
            style_preference,
        )
        if luxury_style:
            if any(term in item_metadata for term in (
                "tailored", "structured", "silk", "blazer", "executive",
                "luxury", "premium", "elegant", "formal", "sophisticated",
                "traditional", "myanmar", "heel", "leather", "watch", "jewelry",
            )):
                item_score += 35
            if any(term in item_metadata for term in (
                "cute", "sexy", "playful", "casual", "everyday",
                "streetwear", "jeans", "denim", "hoodie", "basic",
            )):
                item_score -= 80
        if body_fit_goal:
            if any(term in item_metadata for term in (
                "high waist", "high-waist", "tailored", "fitted", "tucked",
                "vertical", "monochrome", "pointed", "short jacket", "cropped jacket",
            )):
                item_score += 45
            if any(term in item_metadata for term in (
                "oversized", "heavy", "long bulky", "low waist", "low-rise",
            )):
                item_score -= 55
        recent_count = int(item.get("recent_recommendation_count") or 0)
        if recent_count:
            item_score -= min(recent_count * 5, 15)
        color = str(item.get("color") or "").casefold()
        if color in {"purple", "ခရမ်း"} and not any(
            term in normalized_query for term in ("purple", "ခရမ်း")
        ):
            item_score -= 4
        scored[broad_type].append((
            max(0, item_score),
            item,
        ))
    for entries in scored.values():
        entries.sort(key=lambda entry: entry[0], reverse=True)

    if context == "religious_place":
        traditionals = scored["traditional"]
        dresses = scored["dress"]
        tops = scored["top"]
        bottoms = scored["bottom"]
        if traditionals:
            item = _pick_best(traditionals)
            outfit = [_item_label(item)]
        elif dresses:
            item = _pick_best(dresses)
            outfit = [_item_label(item)]
        elif tops and bottoms:
            outfit = [
                _item_label(_pick_best(tops)),
                _item_label(_pick_best(bottoms)),
            ]
        else:
            outfit, _, _ = _build_generic_outfit(
                classified, scored, occasion_key, temperature_c,
            )
        explanation = (
            "I’d choose the most modest piece in your wardrobe for the pagoda. "
            "Keep the styling simple and respectful, with shoulders and knees covered."
        )
    elif context == "business_meeting":
        outfit, explanation, _ = _build_interview_outfit(
            classified, scored, occasion_key, temperature_c,
        )
        business_finishing_pieces = (
            ("blazer", classified["outerwear"]),
            ("watch", classified["accessory"]),
            ("bag", classified["accessory"]),
            ("shoe", classified["shoes"]),
        )
        outfit_text = " ".join(outfit).casefold()
        for keyword, candidates in business_finishing_pieces:
            if keyword in outfit_text:
                continue
            match = next(
                (
                    item for item in candidates
                    if keyword in " ".join(
                        str(item.get(field) or "").casefold()
                        for field in ("category", "subtype", "description")
                    )
                ),
                None,
            )
            if match:
                label = _wardrobe_display_name(match)
                outfit.append(label)
                outfit_text += f" {label.casefold()}"
        explanation = (
            "For a client meeting, I’d take your usual work style one level more polished. "
            + explanation
        )
    elif context == "wedding":
        outfit, explanation, _ = _build_wedding_outfit(
            classified, scored, occasion_key, temperature_c,
        )
    elif luxury_style and profile and str(profile.gender or "").casefold() in {
        "man", "male", "men", "ကျား",
    }:
        outfit, explanation, _ = _build_interview_outfit(
            classified, scored, occasion_key, temperature_c,
        )
    elif occasion_key in {"party", "luxury"}:
        outfit, explanation, _ = _build_party_outfit(
            classified, scored, occasion_key, temperature_c,
        )
    elif occasion_key in {"casual", "fit"}:
        outfit, explanation, _ = _build_casual_outfit(
            classified, scored, occasion_key, temperature_c,
        )
    else:
        outfit, explanation, _ = _build_generic_outfit(
            classified, scored, occasion_key, temperature_c,
        )

    if not outfit:
        return _context_only_outfit(query, profile)
    if body_fit_goal:
        explanation = (
            "This combination supports the fit goal first: keep the waist defined, maintain "
            "a clean vertical line, and avoid oversized layers that break the proportions."
        )
    outfit_text = " ".join(outfit).casefold()
    finishing_specs = (
        (
            ("shoe", "sandal", "loafer", "sneaker", "ဖိနပ်"),
            classified["shoes"],
        ),
        (
            ("bag", "clutch", "tote", "အိတ်"),
            [
                item for item in classified["accessory"]
                if any(term in " ".join(
                    str(item.get(field) or "").casefold()
                    for field in ("category", "subtype", "description")
                ) for term in ("bag", "clutch", "tote", "အိတ်"))
            ],
        ),
        (
            ("watch", "jewelry", "jewellery", "bracelet", "နာရီ", "လက်ဝတ်"),
            [
                item for item in classified["accessory"]
                if any(term in " ".join(
                    str(item.get(field) or "").casefold()
                    for field in ("category", "subtype", "description")
                ) for term in (
                    "watch", "jewelry", "jewellery", "bracelet", "နာရီ", "လက်ဝတ်",
                ))
            ],
        ),
    )
    for keywords, candidates in finishing_specs:
        if candidates and not any(keyword in outfit_text for keyword in keywords):
            item = candidates[0]
            label = _wardrobe_display_name(item)
            outfit.append(label)
            outfit_text += f" {label.casefold()}"
    return {
        "outfit": _complete_outfit_presentation(outfit, query),
        "explanation": explanation,
        "weather_based_tip": _get_weather_tip(None, temperature_c),
    }


def _myanmar_weather_tip(
    weather_desc: str | None,
    temperature_c: float | None,
    humidity: int | None,
    provider_tip: str,
    location: str | None = None,
    query: str = "",
) -> str:
    """Present weather as one practical Myanmar-climate styling note."""
    description = (weather_desc or "").casefold()
    place = f" in {location}" if location else ""
    if any(term in description for term in ("rain", "shower", "storm", "မိုး")):
        return (
            f"Rain is possible{place}, so bring a compact umbrella and wear shoes "
            "that can handle wet streets."
        )
    if (temperature_c is not None and temperature_c >= 30) or (
        humidity is not None and humidity >= 70
    ):
        return (
            f"It’ll feel hot and humid{place}, so keep your layers light and choose "
            "breathable fabric."
        )
    if temperature_c is not None and temperature_c < 22:
        return (
            f"It may feel cooler later{place}, so bring one light layer "
            "you can take off easily."
        )
    if location and weather_desc:
        return (
            f"The weather in {location} looks comfortable; keep your layer "
            "light and easy to carry."
        )
    provider_copy = provider_tip.strip()
    generic_tip = provider_copy.casefold()
    if provider_copy and not any(term in generic_tip for term in (
        "dress for the weather",
        "suitable for the weather",
        "according to the weather",
        "ရာသီဥတုနဲ့လိုက်ဖက်",
    )):
        return provider_copy

    context = classify_occasion_context(query)
    return {
        "religious_place": (
            "Choose comfortable sandals that are easy to remove because you may walk "
            "and take your shoes off often."
        ),
        "date": (
            "Bring a light cardigan because cafés and cinemas can feel cold inside."
        ),
        "dinner": (
            "Keep one light layer nearby in case the restaurant is cool."
        ),
        "wedding": (
            "A light shawl is useful for cool indoor venues without covering the outfit."
        ),
        "travel": (
            "Choose comfortable shoes and carry one light layer for changing temperatures."
        ),
        "work": (
            "Bring a light layer for air-conditioned rooms and keep it easy to carry."
        ),
    }.get(
        context,
        "Choose breathable fabric and keep one light layer nearby for cooler indoor spaces.",
    )


def _profile_context(profile: Profile | None) -> dict[str, Any]:
    """Return recommendation-safe user profile fields for AI providers."""
    if profile is None:
        return {}
    fields = (
        "gender",
        "height_cm",
        "top_size",
        "bottom_size",
        "shoe_size",
        "skin_tone",
        "style_preference",
        "fit_preference",
        "outfit_vibe",
        "preferred_colors",
        "shopping_style",
        "location_city",
        "location_area",
    )
    return {
        field: getattr(profile, field)
        for field in fields
        if getattr(profile, field) not in (None, "")
    }


def _wardrobe_context_item(item: Wardrobe) -> dict[str, Any]:
    """Serialize useful wardrobe metadata without blank optional values."""
    fields = (
        "category",
        "subtype",
        "color",
        "style_tags",
        "occasion_tags",
        "material_tags",
        "brand",
        "formality_level",
        "season_suitability",
        "description",
    )
    context: dict[str, Any] = {"id": item.id}
    if item.cloudinary_url:
        context["url"] = item.cloudinary_url
    for field in fields:
        value = getattr(item, field, None)
        if isinstance(value, str):
            value = value.strip()
        if value not in (None, ""):
            context[field] = value
    return context


def _annotate_recent_recommendations(
    wardrobe_items: list[dict[str, Any]],
    recent_responses: list[str],
) -> list[dict[str, Any]]:
    """Mark recently used pieces/colors so providers can vary equal choices."""
    normalized_responses = [response.casefold() for response in recent_responses if response]
    for item in wardrobe_items:
        terms = {
            str(item.get(field) or "").strip().casefold()
            for field in ("subtype", "color", "description")
            if str(item.get(field) or "").strip()
        }
        count = sum(
            1
            for response in normalized_responses
            if any(term in response for term in terms)
        )
        if count:
            item["recent_recommendation_count"] = count
    return wardrobe_items


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
    style_tags = (item.get("style_tags") or "").lower().strip()
    occasion_tags = (item.get("occasion_tags") or "").lower().strip()
    formality = (item.get("formality_level") or "").lower().strip()
    metadata = f"{cat} {sub} {desc} {style_tags} {occasion_tags} {formality}"
    occ_lower = occasion.lower().strip()
    score = 0

    # --- Occasion category fit ---
    if occ_lower == "temple":
        if broad_type == "traditional":
            score += 50
        elif broad_type in ("top", "bottom"):
            score += 32
        elif broad_type == "dress":
            score += 20
        elif broad_type == "shoes":
            score += 12
        else:
            score += 5
        if any(term in metadata for term in (
            "sexy", "mini", "revealing", "low-cut", "crop top", "party",
            "ပေါ်လွင်", "တိုတို",
        )):
            score -= 70
        if any(term in metadata for term in (
            "modest", "traditional", "covered", "longyi", "htamein",
            "မြန်မာ", "ရိုးရာ", "လုံချည်", "ထဘီ",
        )):
            score += 18
        if any(term in metadata for term in (
            "comfortable", "walking", "breathable", "ပေါ့ပါး",
        )):
            score += 6
    elif occ_lower == "interview":
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
        if any(term in metadata for term in (
            "formal", "smart casual", "tailored", "structured", "polished",
        )):
            score += 8
        if any(term in metadata for term in (
            "streetwear", "sport", "distressed", "lounge", "beach",
        )) or sub in ("hoodie", "shorts", "tank top"):
            score -= 18
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
    elif occ_lower in {"party", "dinner", "luxury"}:
        # Formal social occasion: occasion fit dominates color harmony.
        if broad_type == "dress":
            score += 40
        elif broad_type == "traditional":
            score += 38
        elif broad_type in ("top", "bottom"):
            score += 20
        else:
            score += 10
        if any(term in metadata for term in (
            "formal", "elegant", "refined", "party", "evening",
            "structured", "heel", "jewelry", "jewellery", "watch",
            "traditional", "myanmar", "longyi", "htamein",
        )):
            score += 20
        if any(term in metadata for term in (
            "jeans", "denim", "hoodie", "streetwear", "sportswear",
            "sneaker", "everyday", "basic", "casual",
        )):
            score -= 35
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
        if outerwear:
            labels.append(_item_label(_pick_best(outerwear)))
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
    traditionals = scored.get("traditional", [])
    tops = scored.get("top", [])
    bottoms = scored.get("bottom", [])
    dresses = scored.get("dress", [])
    outerwear = scored.get("outerwear", [])
    occasion_my_str = _occasion_my(occasion)

    # ── Separate party-specific dresses from general dresses ──
    party_dress_subtypes = {"party dress", "formal dress", "evening dress"}
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

    # Good: refined Myanmar traditional wear before casual dresses.
    if traditionals:
        traditional = _pick_best(traditionals)
        s = traditionals[0][0]
        label = _item_label(traditional)
        explanation = (
            f"ပါတီအတွက် {label} က ဖိတ်ကြားထားတဲ့ပွဲနဲ့လိုက်ဖက်ပြီး "
            f"မြန်မာဆန်ဆန် ကြော့ရှင်းတဲ့ look ဖြစ်ပါတယ်။"
        )
        return ([label], explanation, s)

    # Good: bold party dress (red, black, etc.), after garment formality.
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
        if outerwear:
            labels.append(_item_label(_pick_best(outerwear)))
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

    Fetches the user's profile + manually described wardrobe and current
    weather, then asks OpenRouter first for a text-only recommendation.

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
    recent_sessions = (
        db.query(StyleSession)
        .filter(StyleSession.user_id == user_id)
        .order_by(StyleSession.created_at.desc())
        .limit(5)
        .all()
    )
    recommendation_query = _recommendation_query_with_recent_context(
        body.occasion,
        recent_sessions,
    )
    requested_occasion = body.occasion
    body = RecommendRequest(occasion=recommendation_query)

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

        visual_request = is_visual_comparison_request(body.occasion)
        source = "fallback" if visual_request else "api_error"
        ai_result: dict[str, Any] | None = (
            _visual_comparison_fallback([], body.occasion)
            if visual_request
            else None
        )
        profile_data = _profile_context(profile)

        # 1. Try OpenRouter first
        if ai_result is None and settings.openrouter_api_key:
            try:
                ai_result = openrouter_recommend(
                    **_ai_kwargs,
                    profile_data=profile_data,
                )
                if ai_result is not None:
                    source = "openrouter"
                    logger.info("[WUTT] source=openrouter endpoint=/recommend no_wardrobe=True")
            except Exception as exc:
                logger.warning("[WUTT] source=api_error endpoint=/recommend openrouter_error=%s", type(exc).__qualname__)

        # 2. Try OpenAI
        if ai_result is None and settings.openai_api_key:
            try:
                ai_result = openai_recommend(**_ai_kwargs)
                if ai_result is not None:
                    source = "openai"
                    logger.info("[WUTT] source=openai endpoint=/recommend no_wardrobe=True")
            except Exception as exc:
                logger.warning("[WUTT] source=api_error endpoint=/recommend openai_error=%s", type(exc).__qualname__)

        # 3. Try Gemini
        if ai_result is None and settings.gemini_api_key:
            try:
                ai_result = gemini_recommend(**_ai_kwargs)
                if ai_result is not None:
                    source = "gemini"
                    logger.info("[WUTT] source=gemini endpoint=/recommend no_wardrobe=True")
            except Exception as exc:
                logger.warning("[WUTT] source=api_error endpoint=/recommend gemini_error=%s", type(exc).__qualname__)

        # A clear outfit request always receives an immediate complete look.
        if (
            (ai_result is None or not ai_result.get("outfit"))
            and not visual_request
        ):
            source = "fallback"
            logger.info("[WUTT] source=fallback endpoint=/recommend reason=no_usable_ai_outfit")
            ai_result = (
                _accessory_selection_fallback([], body.occasion)
                if accessory_selection_type(body.occasion)
                else (
                    _shopping_fallback(body.occasion, profile)
                    if is_shopping_intent(body.occasion)
                    else _context_only_outfit(body.occasion, profile)
                )
            )

        outfit, explanation, weather_based_tip = _extract_outfit_fields(ai_result)
        outfit = _normalize_outfit_labels(outfit, [])
        if not accessory_selection_type(body.occasion):
            outfit = _complete_outfit_presentation(outfit, body.occasion)
        explanation = _remove_technical_ids(explanation, [])
        explanation = _remove_unowned_possessives(explanation, [])
        explanation = _refine_marketing_tag_language(explanation, body.occasion)
        weather_based_tip = _myanmar_weather_tip(
            None,
            None,
            None,
            weather_based_tip,
            query=body.occasion,
        )
        ai_result["outfit"] = outfit
        ai_result["explanation"] = explanation
        ai_result["weather_based_tip"] = weather_based_tip

        # Save session for history
        session = StyleSession(
            user_id=user_id,
            occasion=_session_occasion(requested_occasion),
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
            "message": "Add a few favorite pieces and I’ll make this look more personal.",
        }

    logger.info(
        "POST /stylist/recommend — user_id=%d item_count=%d calling AI providers",
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

    # ── Prepare text-first wardrobe context ─────────────
    wardrobe_images: list[dict[str, Any]] = []
    for item in items:
        wardrobe_images.append(_wardrobe_context_item(item))
    _annotate_recent_recommendations(
        wardrobe_images,
        [session.ai_response or "" for session in recent_sessions],
    )
    wardrobe_images = _rank_wardrobe_context(
        wardrobe_images,
        body.occasion,
        profile,
    )

    # ── Provider chain: OpenRouter → OpenAI → Gemini → graceful result ──
    visual_request = is_visual_comparison_request(body.occasion)
    source: str = "fallback" if visual_request else "api_error"
    ai_result: dict[str, Any] | None = (
        _visual_comparison_fallback(wardrobe_images, body.occasion)
        if visual_request
        else None
    )

    logger.info(
        "[WUTT] source=init endpoint=/recommend user_id=%d openrouter_key=%s openai_key=%s gemini_key=%s",
        user_id, bool(settings.openrouter_api_key), bool(settings.openai_api_key), bool(settings.gemini_api_key),
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

    # 1. Try OpenRouter first
    if ai_result is None and settings.openrouter_api_key:
        try:
            ai_result = openrouter_recommend(
                **_ai_kwargs,
                profile_data=_profile_context(profile),
            )
            if ai_result is not None:
                source = "openrouter"
                logger.info("[WUTT] source=openrouter endpoint=/recommend items=%d", len(ai_result.get("outfit", [])))
            else:
                logger.info("[WUTT] source=openrouter endpoint=/recommend result=None → trying OpenAI")
        except Exception as exc:
            cls = type(exc).__qualname__
            mod = type(exc).__module__
            logger.warning("[WUTT] source=api_error endpoint=/recommend openrouter_error=%s.%s", mod, cls)

    # 2. Try OpenAI if OpenRouter didn't return a result
    if ai_result is None and settings.openai_api_key:
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

    # 3. Try Gemini if OpenAI didn't return a result
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

    if (
        ai_result
        and _executive_outfit_conflicts(
            ai_result.get("outfit") or [],
            wardrobe_images,
            body.occasion,
        )
    ):
        logger.info(
            "[WUTT] source=fallback endpoint=/recommend "
            "reason=provider_style_conflicts_with_executive_request"
        )
        ai_result = None

    # A clear outfit request always receives a wardrobe-aware complete look.
    if (
        (ai_result is None or not ai_result.get("outfit"))
        and not visual_request
    ):
        source = "fallback"
        logger.info("[WUTT] source=fallback endpoint=/recommend reason=no_usable_ai_outfit")
        ai_result = (
            _accessory_selection_fallback(wardrobe_images, body.occasion)
            if accessory_selection_type(body.occasion)
            else (
                _shopping_fallback(body.occasion, profile)
                if is_shopping_intent(body.occasion)
                else _wardrobe_fallback_outfit(
                    wardrobe_images,
                    body.occasion,
                    temperature_c,
                    profile,
                )
            )
        )

    outfit, explanation, weather_based_tip = _extract_outfit_fields(ai_result)
    outfit = _normalize_outfit_labels(outfit, wardrobe_images)
    outfit = _preserve_requested_base(outfit, body.occasion, wardrobe_images)
    if not accessory_selection_type(body.occasion):
        outfit = _complete_outfit_presentation(outfit, body.occasion)
    explanation = _remove_technical_ids(explanation, wardrobe_images)
    explanation = _remove_unowned_possessives(explanation, wardrobe_images)
    explanation = _personalize_explanation(
        explanation,
        outfit,
        wardrobe_images,
    )
    explanation = _refine_marketing_tag_language(explanation, body.occasion)
    weather_based_tip = _myanmar_weather_tip(
        weather_desc,
        temperature_c,
        humidity,
        weather_based_tip,
        location,
        body.occasion,
    )
    ai_result["outfit"] = outfit
    ai_result["explanation"] = explanation
    ai_result["weather_based_tip"] = weather_based_tip

    # ── Save session ───────────────────────────────────
    session = StyleSession(
        user_id=user_id,
        occasion=_session_occasion(requested_occasion),
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
        "message": "Here’s the look I’d pick for you.",
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
        wardrobe_context.append(_wardrobe_context_item(item))

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
    profile_context = _profile_context(profile)
    if profile_context:
        knowledge_context += (
            "\n\n[User Profile — use naturally and do not repeat as a list]\n"
            + json.dumps(profile_context, ensure_ascii=False)
        )

    # ── Call real AI only — no fake fallback ──────────────
    visual_request = is_visual_comparison_request(message)
    source = "fallback" if visual_request else "api_error"
    response_text: str | None = (
        _visual_comparison_fallback(wardrobe_context, message)["explanation"]
        if visual_request
        else None
    )
    last_error: str = ""

    # Build enriched message once (shared across providers)
    enriched_message = message
    if knowledge_context:
        enriched_message = message + knowledge_context

    # 1. Try OpenRouter (primary)
    if not response_text and settings.openrouter_api_key:
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
        source = "fallback"
        has_context = classify_occasion_context(message) != "general"
        mentions_item = _query_mentions_clothing(message)
        if wardrobe_context:
            response_text = _chat_wardrobe_fallback(
                message,
                wardrobe_context,
                profile,
            )
        elif has_context:
            response_text = _format_chat_recommendation(
                _context_only_outfit(message, profile)
            )
        elif mentions_item:
            response_text = (
                "I couldn’t find that exact piece in your saved wardrobe. Add its "
                "details and I’ll style around it without substituting another item."
            )
        else:
            response_text = (
                "Tell me one piece you want to wear and the occasion, and I’ll help "
                "you build around it."
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


@router.delete("/history/{user_id}/today")
def delete_today_history(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuthResponse:
    """Delete only the current UTC day's style sessions for the signed-in user."""
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail={
                "status": "error",
                "data": {},
                "message": "You can only delete your own style history.",
            },
        )

    today = datetime.now(timezone.utc).date().isoformat()
    deleted = (
        db.query(StyleSession)
        .filter(
            StyleSession.user_id == user_id,
            func.date(StyleSession.created_at) == today,
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return {
        "status": "success",
        "data": {"deleted": deleted},
        "message": "Today's chat was deleted.",
    }
