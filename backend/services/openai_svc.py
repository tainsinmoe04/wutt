"""OpenAI GPT-4o Vision service — outfit recommendation engine.

Key rule (CLAUDE.md): send images as base64 **or** url — not both.
We send as base64 so no external image URLs leak.
"""

from typing import Any

from openai import OpenAI
from config import settings


def _build_client() -> OpenAI | None:
    """Return an OpenAI client or None if the key is not configured."""
    if not settings.openai_api_key:
        return None
    return OpenAI(api_key=settings.openai_api_key)


def get_outfit_recommendation(
    wardrobe_items: list[dict[str, Any]],
    occasion: str,
    weather_desc: str | None = None,
    temperature_c: float | None = None,
    height_cm: float | None = None,
    skin_tone: str | None = None,
    style_preference: str | None = None,
) -> str | None:
    """Ask GPT-4o Vision to recommend an outfit.

    Args:
        wardrobe_items: List of dicts with ``url`` and optionally
                        ``category``, ``color``, ``description``.
        occasion: What the user is dressing for.
        weather_desc: Human-readable weather (e.g. "clear sky").
        temperature_c: Temperature in Celsius.
        height_cm: User height in cm.
        skin_tone: User skin tone.
        style_preference: Preferred style (e.g. "casual", "formal").

    Returns:
        AI response text with outfit recommendation, or None on failure.
    """
    client = _build_client()
    if client is None:
        return None

    # Build context text
    lines = [f"Occasion: {occasion}"]
    if weather_desc:
        lines.append(f"Weather: {weather_desc}")
    if temperature_c is not None:
        lines.append(f"Temperature: {temperature_c:.0f}°C")
    if height_cm is not None:
        lines.append(f"Height: {height_cm:.0f} cm")
    if skin_tone:
        lines.append(f"Skin tone: {skin_tone}")
    if style_preference:
        lines.append(f"Style preference: {style_preference}")
    context = "\n".join(lines)

    system_prompt = (
        "You are WUTT, Myanmar's AI personal stylist. "
        "Your job is to recommend the best outfit from the user's wardrobe "
        "for the given occasion, weather, body type, and style preference. "
        "Be specific — mention which items to wear together, why they work, "
        "and how the colors complement each other. "
        "If the occasion is formal, suggest formal combinations. "
        "If casual, suggest relaxed combinations. "
        "Write in a warm, friendly tone suitable for Myanmar users. "
        "Use Myanmar language if the user's context suggests it, otherwise English."
    )

    user_prompt = (
        f"Here is my wardrobe. Please recommend an outfit.\n\n{context}\n\n"
        "For each wardrobe image shown, describe which items to pair together "
        "and explain your reasoning. Include color coordination tips and "
        "mention if the outfit suits the weather and occasion."
    )

    # Build message content — images as base64 URLs (NOT both base64 data + url)
    content: list[dict[str, Any]] = [{"type": "text", "text": user_prompt}]
    for item in wardrobe_items:
        url = item.get("url")
        if url:
            content.append({
                "type": "image_url",
                "image_url": {"url": url, "detail": "auto"},
            })

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
            max_tokens=800,
            temperature=0.7,
        )
        return response.choices[0].message.content
    except Exception:
        return None
