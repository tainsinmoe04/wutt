"""OpenAI GPT-4o Vision service — outfit recommendation engine.

Two modes:
  • Vision mode (default) — sends wardrobe images as Cloudinary URLs to
    GPT-4o Vision and asks it to analyse them visually.
  • Text-only mode — activated automatically when *OPENAI_BASE_URL* is set
    (e.g. an OpenAI-compatible proxy such as VibeCode that may not support
    vision/image input).  Builds a rich descriptive prompt from wardrobe
    metadata (category, colour, description) + user profile + weather.

Key rule (CLAUDE.md): send images as base64 **or** url — not both.
"""

# NOTE: This module also provides get_chat_response() as a fallback
# when Gemini quota is exhausted.  The chat prompt mirrors gemini_svc.py.

import json
import logging
from typing import Any

from openai import OpenAI
from config import settings

logger = logging.getLogger(__name__)


def _build_client() -> OpenAI | None:
    """Return an OpenAI client or None if the key is not configured.

    When *openai_base_url* is set (e.g. an OpenAI-compatible proxy such as
    VibeCode), the client is pointed at that endpoint instead of the default.
    """
    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY is not set — AI recommendations disabled")
        return None
    kwargs: dict[str, Any] = {"api_key": settings.openai_api_key}
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return OpenAI(**kwargs)


def _build_text_only_user_prompt(
    wardrobe_items: list[dict[str, Any]],
    occasion: str,
    weather_desc: str | None = None,
    temperature_c: float | None = None,
    humidity: int | None = None,
    height_cm: float | None = None,
    skin_tone: str | None = None,
    style_preference: str | None = None,
) -> str:
    """Build a rich text prompt describing the wardrobe **without images**.

    Used when OPENAI_BASE_URL points to an OpenAI-compatible proxy that does
    not support GPT-4o-style vision/image input.  The prompt includes every
    available piece of metadata so the model can make a reasonable pick.
    """
    lines: list[str] = []

    # ── Wardrobe inventory ──────────────────────────────
    lines.append("My wardrobe items:")
    if not wardrobe_items:
        lines.append("  (no items listed)")
    else:
        for i, item in enumerate(wardrobe_items, 1):
            parts: list[str] = []
            cat = item.get("category")
            if cat:
                parts.append(str(cat))
            col = item.get("color")
            if col:
                parts.append(str(col))
            desc = item.get("description")
            if desc:
                parts.append(f"— {desc}")
            lines.append(f"  {i}. {' '.join(parts) if parts else '(unnamed item)'}")

    # ── Context ─────────────────────────────────────────
    lines.append("")
    lines.append(f"Occasion: {occasion}")
    if weather_desc:
        lines.append(f"Weather: {weather_desc}")
    if temperature_c is not None:
        lines.append(f"Temperature: {temperature_c:.0f}°C")
    if humidity is not None:
        lines.append(f"Humidity: {humidity}%")
    if height_cm is not None:
        lines.append(f"My height: {height_cm:.0f} cm")
    if skin_tone:
        lines.append(f"My skin tone: {skin_tone}")
    if style_preference:
        lines.append(f"My style preference: {style_preference}")

    # ── Instruction ─────────────────────────────────────
    lines.append("")
    lines.append(
        "Please recommend the best outfit from the items listed above "
        "for this occasion and weather.  "
        "Return a JSON object with outfit[], explanation, and weather_based_tip."
    )

    return "\n".join(lines)


# ── Shared system prompt (used by both vision and text-only modes) ──

_SYSTEM_PROMPT = (
    "You are WUTT, Myanmar's AI personal stylist. "
    "Analyse the user's wardrobe and recommend the best outfit "
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
    "- Recommend only from the wardrobe items listed in the prompt.\n"
    "- If there are no usable items, return an empty outfit array.\n"
    "- Use warm, friendly Myanmar-style language for explanation and tip.\n"
    "- Be specific about colours and categories.\n"
    "- If the occasion is formal, prefer formal combinations.\n"
    "- If casual, prefer relaxed combinations."
)


def _parse_ai_response(raw: str | None) -> dict[str, Any] | None:
    """Parse the model's JSON response, stripping markdown fences if present."""
    if not raw:
        return None
    text = raw.strip()
    if text.startswith("```"):
        # Remove opening fence (```json or ```)
        text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
        # Remove closing fence
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    parsed = json.loads(text)
    return {
        "outfit": parsed.get("outfit", []),
        "explanation": parsed.get("explanation", ""),
        "weather_based_tip": parsed.get("weather_based_tip", ""),
    }


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
    """Ask the AI model to recommend an outfit.

    When *OPENAI_BASE_URL* is set (proxy mode) this function builds a
    text-only prompt from wardrobe metadata and does **not** send images —
    many OpenAI-compatible proxies / alternative models do not support
    GPT-4o-style vision input.

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

    is_proxy_mode = bool(settings.openai_base_url)

    # ── Build message content ───────────────────────────
    if is_proxy_mode:
        # Text-only: describe wardrobe items, do NOT send images.
        # Many OpenAI-compatible proxies don't support vision/image_url.
        logger.info("PROXY_TEXT_ONLY_MODE model=%s", settings.openai_model)
        user_prompt = _build_text_only_user_prompt(
            wardrobe_items=wardrobe_items,
            occasion=occasion,
            weather_desc=weather_desc,
            temperature_c=temperature_c,
            humidity=humidity,
            height_cm=height_cm,
            skin_tone=skin_tone,
            style_preference=style_preference,
        )
        # Plain string — many OpenAI-compatible proxies reject content-as-array
        content = user_prompt
    else:
        # Vision mode: send wardrobe images as Cloudinary URLs.
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

        user_prompt = (
            "Here is my wardrobe. Please recommend an outfit.\n\n"
            f"{context}\n\n"
            "Return a JSON object with outfit[], explanation, and weather_based_tip."
        )
        content = [{"type": "text", "text": user_prompt}]
        for item in wardrobe_items:
            url = item.get("url")
            if url:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": url, "detail": "auto"},
                })

    try:
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            max_tokens=800,
            temperature=0.7,
        )
        return _parse_ai_response(response.choices[0].message.content)
    except Exception as exc:
        # ── Safe server-side logging — never log the API key ──
        cls = type(exc).__qualname__
        mod = type(exc).__module__
        status = getattr(exc, "status_code", None)
        code = getattr(exc, "code", None)
        body = getattr(exc, "body", None)
        msg = getattr(exc, "message", None) or str(exc)

        logger.error(
            "OpenAI API call failed: %s.%s | status=%s code=%s message=%s",
            mod, cls, status, code, msg,
        )
        if body is not None:
            logger.error("OpenAI error body: %s", body)
        return None


# ── General Chat (fallback for Gemini) ────────────────────

_CHAT_SYSTEM_PROMPT = (
    "You are WUTT, a friendly AI fashion companion for Myanmar users. "
    "You are NOT a generic assistant — you are a personal stylist and "
    "fashion friend who knows fashion, fit, colour theory, and Myanmar culture.\n\n"
    "Tone: warm, natural, short, useful — like a stylish friend texting. "
    "Never say 'As an AI…' or 'I'm an AI assistant'. Just be helpful.\n\n"
    "You can help with:\n"
    "- General fashion questions (what to wear, colour matching, style tips)\n"
    "- Explaining how to use WUTT (upload clothes, get recommendations, save looks)\n"
    "- Casual chat about fashion, style, occasions\n"
    "- Outfit recommendations when asked specifically\n\n"
    "Knowledge:\n"
    "- Use fashion knowledge for style advice (color rules, occasion rules, trends).\n"
    "- Use the app guide when users ask how WUTT works.\n"
    "- Always consider Myanmar climate (hot, monsoon, cool seasons) when giving advice.\n"
    "- Know Myanmar cultural occasions (wedding, temple, longyi style).\n\n"
    "Rules:\n"
    "- Keep responses short (2-4 sentences usually).\n"
    "- Be warm and Myanmar-friendly.\n"
    "- If the user asks what to wear for a specific occasion, give 2-3 practical outfit ideas.\n"
    "- If the user asks how to use WUTT, explain the app simply.\n"
    "- If the user just says hi/hey, greet them back warmly and ask how you can help.\n"
    "- Never fabricate wardrobe items — only reference items the user has mentioned.\n"
    "- Mix English and Myanmar naturally when it feels right."
)


def get_chat_response(
    user_message: str,
    conversation_history: list[dict[str, str]] | None = None,
    wardrobe_items: list[dict[str, Any]] | None = None,
) -> str | None:
    """General chat via OpenAI — fallback when Gemini quota is exhausted.

    Mirrors the interface of gemini_svc.get_chat_response() so the route
    can swap providers transparently.

    Args:
        user_message: The user's latest message.
        conversation_history: Previous messages as [{"role": "user"|"bot", "content": "..."}].
        wardrobe_items: Optional wardrobe context for personalised advice.

    Returns:
        Natural text response, or None on failure.
    """
    client = _build_client()
    if client is None:
        return None

    # Build messages array for OpenAI chat format
    messages: list[dict[str, str]] = [
        {"role": "system", "content": _CHAT_SYSTEM_PROMPT},
    ]

    # Add wardrobe context as a system note
    if wardrobe_items:
        wardrobe_lines = ["User's wardrobe items:"]
        for i, item in enumerate(wardrobe_items[:10], 1):
            cat = item.get("category", "")
            color = item.get("color", "")
            desc = item.get("description", "")
            parts = [p for p in [cat, color, desc] if p]
            wardrobe_lines.append(f"  {i}. {' '.join(parts) if parts else '(unnamed)'}")
        messages.append({"role": "system", "content": "\n".join(wardrobe_lines)})

    # Add conversation history
    if conversation_history:
        for msg in conversation_history[-8:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "bot"):
                messages.append({
                    "role": "assistant" if role == "bot" else "user",
                    "content": content,
                })

    # Add current user message
    messages.append({"role": "user", "content": user_message})

    try:
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            max_tokens=500,
            temperature=0.8,
        )
        raw = response.choices[0].message.content
        if raw:
            return raw.strip()
        return None
    except Exception as exc:
        cls = type(exc).__qualname__
        mod = type(exc).__module__
        status = getattr(exc, "status_code", None)
        code = getattr(exc, "code", None)
        msg = getattr(exc, "message", None) or str(exc)
        logger.error(
            "OpenAI chat failed: %s.%s | status=%s code=%s message=%s",
            mod, cls, status, code, msg,
        )
        return None
