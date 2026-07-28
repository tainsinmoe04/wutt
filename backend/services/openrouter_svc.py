"""OpenRouter service for WUTT stylist chat responses.

OpenRouter uses an OpenAI-compatible API, so we reuse the openai client
with a custom base URL.  This is the primary provider — Gemini and OpenAI
are fallbacks.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import json

from openai import OpenAI

from config import settings
from services.stylist_prompt import (
    WUTT_PERSONALITY_PROMPT,
    WUTT_RECOMMENDATION_PROMPT,
    occasion_context_prompt,
    recommendation_mode_prompt,
)

logger = logging.getLogger(__name__)

# ── Shared system prompt ──────────────────────────────────────
_CHAT_SYSTEM_PROMPT = WUTT_PERSONALITY_PROMPT


def _build_client() -> OpenAI | None:
    """Build OpenAI-compatible client for OpenRouter."""
    api_key = settings.openrouter_api_key
    base_url = settings.openrouter_base_url or "https://openrouter.ai/api/v1"
    if not api_key:
        logger.warning("OPENROUTER_API_KEY not set — OpenRouter provider disabled")
        return None
    return OpenAI(api_key=api_key, base_url=base_url)


def _build_messages(
    user_message: str,
    conversation_history: list[dict[str, str]] | None = None,
    wardrobe_items: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """Build chat messages in OpenAI format."""
    messages = [{"role": "system", "content": _CHAT_SYSTEM_PROMPT}]

    # Add wardrobe context
    if wardrobe_items:
        wardrobe_lines = ["Here are items from the user's wardrobe:"]
        for item in wardrobe_items[:20]:
            name = item.get("name", "Unnamed item")
            category = item.get("category", "")
            color = item.get("color", "")
            season = item.get("season", "")
            wardrobe_lines.append(f"- {name} ({category}, {color}, {season})")
        wardrobe_lines.append(
            "\nReference these items when giving outfit advice."
        )
        messages.append({"role": "user", "content": "\n".join(wardrobe_lines)})
        messages.append({"role": "assistant", "content": "Got it! I can see the items in your wardrobe. I'll keep these in mind when suggesting outfits."})

    # Add conversation history
    if conversation_history:
        for msg in conversation_history[-10:]:
            role = "assistant" if msg.get("role") == "bot" else "user"
            messages.append({
                "role": role,
                "content": msg.get("content") or msg.get("text", ""),
            })

    # Add current message
    messages.append({"role": "user", "content": user_message})

    return messages


def get_chat_response(
    user_message: str,
    conversation_history: list[dict[str, str]] | None = None,
    wardrobe_items: list[dict[str, Any]] | None = None,
) -> str | None:
    """Send a chat message to OpenRouter and return the response text.

    Mirrors gemini_svc.get_chat_response() for transparent provider swapping.
    Returns None if OpenRouter is not configured or the request fails.
    """
    client = _build_client()
    if not client:
        return None

    model = settings.openrouter_ai_model or "openai/gpt-oss-20b:free"

    try:
        messages = _build_messages(
            user_message,
            conversation_history=conversation_history,
            wardrobe_items=wardrobe_items,
        )

        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=1024,
        )

        content = completion.choices[0].message.content
        if content:
            return content.strip()
        logger.warning("OpenRouter returned empty response")
        return None

    except Exception as exc:
        cls = type(exc).__qualname__
        mod = type(exc).__module__
        status = getattr(exc, 'status_code', None) or getattr(exc, 'status', None)
        msg = str(exc)[:200]
        logger.error("OpenRouter chat failed: %s.%s | status=%s — %s", mod, cls, status, msg)
        return None


def get_outfit_recommendation(
    wardrobe_items: list[dict[str, Any]],
    occasion: str,
    weather_desc: str | None = None,
    temperature_c: float | None = None,
    humidity: int | None = None,
    height_cm: float | None = None,
    skin_tone: str | None = None,
    style_preference: str | None = None,
    profile_data: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Generate outfit recommendation using OpenRouter."""

    client = _build_client()
    if client is None:
        return None

    wardrobe_lines: list[str] = []
    for index, item in enumerate(wardrobe_items, 1):
        parts = [f"id={item.get('id', index)}"]
        for key in (
            "category", "subtype", "color", "style_tags", "occasion_tags",
            "material_tags", "brand", "formality_level",
            "season_suitability", "description",
            "recent_recommendation_count",
        ):
            value = item.get(key)
            if value not in (None, ""):
                parts.append(f"{key}={value}")
        wardrobe_lines.append("- " + "; ".join(parts))
    wardrobe_text = "\n".join(wardrobe_lines) or "(no wardrobe items)"

    profile = dict(profile_data or {})
    if height_cm is not None:
        profile.setdefault("height_cm", height_cm)
    if skin_tone:
        profile.setdefault("skin_tone", skin_tone)
    if style_preference:
        profile.setdefault("style_preference", style_preference)
    profile_text = json.dumps(profile, ensure_ascii=False, sort_keys=True)

    prompt = f"""
User profile:
{profile_text}

Wardrobe items:
{wardrobe_text}

Occasion:
{occasion}

{recommendation_mode_prompt(occasion)}

{occasion_context_prompt(occasion)}

Weather:
{weather_desc}

Style preference:
{style_preference}

{WUTT_RECOMMENDATION_PROMPT}
"""

    try:
        completion = client.chat.completions.create(
            model=settings.openrouter_ai_model,
            messages=[
                {
                    "role": "system",
                    "content": WUTT_PERSONALITY_PROMPT,
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=800,
        )

        content = completion.choices[0].message.content

        if not content:
            return None

        return _parse_recommendation_response(content)

    except Exception as exc:
        logger.error("OpenRouter recommend failed: %s", exc)
        return None


def _parse_recommendation_response(raw: str | None) -> dict[str, Any] | None:
    """Parse and normalize structured recommendation JSON from a model."""
    if not raw:
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            logger.warning("OpenRouter recommendation was not JSON")
            return None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            logger.warning("OpenRouter recommendation contained invalid JSON")
            return None

    if not isinstance(parsed, dict):
        return None
    outfit_value = parsed.get("outfit", [])
    if isinstance(outfit_value, str):
        outfit = [outfit_value] if outfit_value.strip() else []
    elif isinstance(outfit_value, list):
        outfit = [
            str(item).strip()
            for item in outfit_value
            if str(item).strip()
        ]
    else:
        outfit = []

    return {
        "outfit": outfit,
        "explanation": str(parsed.get("explanation") or "").strip(),
        "weather_based_tip": str(
            parsed.get("weather_based_tip")
            or parsed.get("weather_tip")
            or ""
        ).strip(),
    }
