"""OpenRouter service for WUTT stylist chat responses.

OpenRouter uses an OpenAI-compatible API, so we reuse the openai client
with a custom base URL.  This is the primary provider — Gemini and OpenAI
are fallbacks.
"""

from __future__ import annotations

import logging
from typing import Any

from openai import OpenAI

from config import settings

logger = logging.getLogger(__name__)

# ── Shared system prompt ──────────────────────────────────────
_CHAT_SYSTEM_PROMPT = """You are WUTT, an AI fashion companion for fashion-interested users.

Core message: "Know Your Wardrobe. Upgrade Your Style."

Personality:
- Fashion-first, AI second — give outfit advice like a trusted stylist friend
- Be warm, encouraging, and visually descriptive
- Suggest specific items, colors, and combinations
- Reference the user's wardrobe items when provided
- Keep responses concise but helpful (2-4 sentences max unless asked for detail)
- Use casual, friendly tone — not robotic or overly formal
- Never lecture — inspire

When responding:
- If wardrobe items are provided, reference them naturally ("That blue blazer in your closet...")
- Suggest complete outfits, not just single pieces
- Consider occasion, weather, and personal style
- If unsure, ask clarifying questions about the occasion or vibe they want"""


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
            messages.append({"role": role, "content": msg.get("text", "")})

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
