"""OpenAI GPT-4o Vision service — outfit recommendation engine.

Key rule (CLAUDE.md): send images as base64 **or** url — not both.
We send images as Cloudinary HTTPS URLs (not base64 data URIs) to avoid
hitting API payload size limits while keeping the implementation simple.
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
    humidity: int | None = None,
    height_cm: float | None = None,
    skin_tone: str | None = None,
    style_preference: str | None = None,
) -> dict[str, Any] | None:
    """Ask GPT-4o Vision to recommend an outfit.

    Args:
        wardrobe_items: List of dicts with ``url`` and optionally
                        ``category``, ``color``, ``description``.
        occasion: What the user is dressing for.
        weather_desc: Human-readable weather (e.g. "clear sky").
        temperature_c: Temperature in Celsius.
        humidity: Relative humidity percentage (0–100).
        height_cm: User height in cm.
        skin_tone: User skin tone.
        style_preference: Preferred style (e.g. "casual", "formal").

    Returns:
        Dict with ``outfit`` (list), ``explanation`` (str),
        ``weather_based_tip`` (str), or None on failure.
    """
    client = _build_client()
    if client is None:
        return None

    # ── Build context block ──────────────────────────────
    lines = [f"Occasion: {occasion}"]
    if weather_desc:
        lines.append(f"Weather: {weather_desc}")
    if temperature_c is not None:
        lines.append(f"Temperature: {temperature_c:.0f}°C")
    if humidity is not None:
        lines.append(f"Humidity: {humidity}%")
    if height_cm is not None:
        lines.append(f"Height: {height_cm:.0f} cm")
    if skin_tone:
        lines.append(f"Skin tone: {skin_tone}")
    if style_preference:
        lines.append(f"Style preference: {style_preference}")
    context = "\n".join(lines)

    # ── System prompt — structured JSON output ───────────
    system_prompt = (
        "You are WUTT, Myanmar's AI personal stylist. "
        "Analyse the user's wardrobe images and recommend the best outfit "
        "for the given occasion, weather, body type, and style preference.\n\n"
        "Return ONLY a JSON object (no markdown fences, no commentary) with these fields:\n"
        '  "outfit": array of strings — each one item to wear, e.g. "Navy blazer (top layer)", '
        '"White linen shirt (base)", "Beige chinos (bottom)". '
        "List 2–5 items in the order they should be worn.\n"
        '  "explanation": string — 2–4 sentences in a warm, friendly tone. '
        "Explain why these items work together, how the colours complement each other, "
        "and how the outfit suits the occasion. Write for a Myanmar audience.\n"
        '  "weather_based_tip": string — one practical tip based on today\'s weather. '
        "If it is hot (>30°C), suggest breathable fabrics or staying cool. "
        "If humid (>70%), mention light, moisture-wicking fabrics. "
        "If cool, suggest layering. If rainy, suggest water-resistant items. "
        "Keep it under 60 characters.\n\n"
        "Rules:\n"
        "- Mention only the items you can see in the images.\n"
        "- If you cannot identify any usable items, return an empty outfit array.\n"
        "- Use warm, friendly Myanmar-style language for explanation and tip.\n"
        "- Be specific about colours and categories.\n"
        "- If the occasion is formal, prefer formal combinations.\n"
        "- If casual, prefer relaxed combinations."
    )

    user_prompt = (
        "Here is my wardrobe. Please recommend an outfit.\n\n"
        f"{context}\n\n"
        "Return a JSON object with outfit[], explanation, and weather_based_tip."
    )

    # ── Build message content — images as URLs ────────────
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
        raw = response.choices[0].message.content
        if not raw:
            return None

        # ── Parse JSON from response ─────────────────────
        import json

        # Strip markdown fences if the model wraps the JSON
        text = raw.strip()
        if text.startswith("```"):
            # Remove opening fence (```json or ```)
            text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
            # Remove closing fence
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        parsed = json.loads(text)

        # Normalise to the expected shape
        return {
            "outfit": parsed.get("outfit", []),
            "explanation": parsed.get("explanation", ""),
            "weather_based_tip": parsed.get("weather_based_tip", ""),
        }
    except Exception:
        return None
