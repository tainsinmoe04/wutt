"""Google Gemini service — outfit recommendation + vision analysis.

Uses the ``google-genai`` package (Gemini 2.0 Flash by default).
When GEMINI_API_KEY is missing, returns None — the caller shows an error.

Phase 2: adds Vision analysis for clothing images and knowledge-file-backed chat.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types as gemini_types
from config import settings

logger = logging.getLogger(__name__)

# ── Load knowledge files ──────────────────────────────────
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

def _load_json(name: str) -> dict[str, Any]:
    """Load a JSON knowledge file from backend/data/."""
    path = _DATA_DIR / name
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("Knowledge file not found: %s", path)
        return {}
    except json.JSONDecodeError:
        logger.warning("Invalid JSON in knowledge file: %s", path)
        return {}

FASHION_KNOWLEDGE: dict[str, Any] = _load_json("fashion_knowledge.json")
APP_GUIDE: dict[str, Any] = _load_json("app_guide.json")


def _build_client() -> genai.Client | None:
    """Return a Gemini client or None if the key is missing."""
    if not settings.gemini_api_key:
        logger.warning("GEMINI_API_KEY is not set — Gemini unavailable")
        return None
    return genai.Client(api_key=settings.gemini_api_key)


# ── System prompt ────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are WUTT, a friendly AI fashion companion for Myanmar users. "
    "You are NOT a generic assistant — you are a personal stylist who "
    "knows fashion, fit, colour theory, and Myanmar culture.\n\n"
    "Tone: warm, natural, like a stylish friend. Never say 'As an AI…' "
    "or 'I'm an AI assistant'. Just give helpful fashion advice.\n\n"
    "When the user asks about how to use WUTT, explain that WUTT is "
    "an AI fashion companion that helps them know their wardrobe and "
    "upgrade their style — upload clothes, get outfit recommendations, "
    "and discover new looks.\n\n"
    "When recommending outfits, analyse the wardrobe items and suggest "
    "the best combination for the occasion, weather, and the user's "
    "style. Be specific about colours and how pieces work together.\n\n"
    "Return ONLY a JSON object (no markdown fences, no commentary) with these fields:\n"
    '  "outfit": array of strings — each one item to wear, '
    'e.g. "Navy blazer (top layer)", "White linen shirt (base)". '
    "List 2–5 items in order.\n"
    '  "explanation": string — 2–4 sentences in a warm, friendly tone. '
    "Explain why these items work together and how they suit the occasion.\n"
    '  "weather_based_tip": string — one practical weather tip, under 60 characters.\n\n'
    "Rules:\n"
    "- Recommend only from the wardrobe items listed in the prompt.\n"
    "- If there are no usable items, return an empty outfit array and "
    "explain what the user should add.\n"
    "- Use warm, Myanmar-friendly language.\n"
    "- Be specific about colours and categories.\n"
    "- If the user asks a general fashion question (not an outfit request), "
    "answer naturally and return a JSON with an empty outfit array and "
    "your helpful answer in the explanation field."
)


def _build_user_prompt(
    wardrobe_items: list[dict[str, Any]],
    occasion: str,
    weather_desc: str | None = None,
    temperature_c: float | None = None,
    humidity: int | None = None,
    height_cm: float | None = None,
    skin_tone: str | None = None,
    style_preference: str | None = None,
) -> str:
    """Build a rich text prompt from wardrobe metadata + context."""
    lines: list[str] = []

    # Wardrobe inventory
    lines.append("My wardrobe items:")
    if not wardrobe_items:
        lines.append("  (empty — no items uploaded yet)")
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

    # Context
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

    # Instruction
    lines.append("")
    lines.append(
        "Please recommend the best outfit from the items listed above "
        "for this occasion and weather. "
        "Return a JSON object with outfit[], explanation, and weather_based_tip."
    )

    return "\n".join(lines)


def _parse_response(raw: str | None) -> dict[str, Any] | None:
    """Parse the model's JSON response, stripping markdown fences if present."""
    if not raw:
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON from surrounding text (some models wrap it)
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            parsed = json.loads(match.group())
        else:
            logger.error("Gemini returned non-JSON: %s", text[:200])
            return None

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
    """Ask Gemini to recommend an outfit.

    Uses text-only mode — Gemini Flash handles text prompts efficiently.
    Image analysis can be added later by sending inline_data parts.

    Args:
        wardrobe_items: List of dicts with ``url``, ``category``, ``color``,
                        ``description``, etc.
        occasion: What the user is dressing for.
        weather_desc: Human-readable weather.
        temperature_c: Temperature in Celsius.
        humidity: Relative humidity (0–100).
        height_cm: User height in cm.
        skin_tone: User skin tone.
        style_preference: Preferred style.

    Returns:
        Dict with ``outfit`` (list), ``explanation`` (str),
        ``weather_based_tip`` (str), or None on failure.
    """
    client = _build_client()
    if client is None:
        return None

    user_prompt = _build_user_prompt(
        wardrobe_items=wardrobe_items,
        occasion=occasion,
        weather_desc=weather_desc,
        temperature_c=temperature_c,
        humidity=humidity,
        height_cm=height_cm,
        skin_tone=skin_tone,
        style_preference=style_preference,
    )

    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=_SYSTEM_PROMPT + "\n\n" + user_prompt,
            config=gemini_types.GenerateContentConfig(
                max_output_tokens=800,
                temperature=0.7,
            ),
        )
        raw = response.text
        logger.info("Gemini response length=%d", len(raw) if raw else 0)
        return _parse_response(raw)
    except Exception as exc:
        cls = type(exc).__qualname__
        mod = type(exc).__module__
        logger.error("Gemini API call failed: %s.%s — %s", mod, cls, exc)
        return None


# ── General Chat ────────────────────────────────────────

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
    """Have a general conversation with Gemini.

    Unlike get_outfit_recommendation, this returns natural text responses
    for general chat, fashion questions, and WUTT explanations.

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

    # Build conversation context
    contents: list[str] = [_CHAT_SYSTEM_PROMPT, ""]

    # Add wardrobe context if available
    if wardrobe_items:
        contents.append("User's wardrobe items:")
        for i, item in enumerate(wardrobe_items[:10], 1):  # Limit to 10 items
            cat = item.get("category", "")
            color = item.get("color", "")
            desc = item.get("description", "")
            parts = [p for p in [cat, color, desc] if p]
            contents.append(f"  {i}. {' '.join(parts) if parts else '(unnamed)'}")
        contents.append("")

    # Add conversation history
    if conversation_history:
        for msg in conversation_history[-8:]:  # Last 8 messages for context
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                contents.append(f"User: {content}")
            else:
                contents.append(f"WUTT: {content}")
        contents.append("")

    # Add current message
    contents.append(f"User: {user_message}")
    contents.append("")
    contents.append("WUTT:")

    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents="\n".join(contents),
            config=gemini_types.GenerateContentConfig(
                max_output_tokens=500,
                temperature=0.8,
            ),
        )
        raw = response.text
        if raw:
            # Clean up response — remove leading/trailing whitespace
            return raw.strip()
        return None
    except Exception as exc:
        cls = type(exc).__qualname__
        mod = type(exc).__module__
        status = getattr(exc, 'status', None)
        msg = str(exc)[:200]
        logger.error("Gemini chat failed: %s.%s | status=%s — %s", mod, cls, status, msg)
        return None


# ── Vision Analysis ───────────────────────────────────────

_VISION_SYSTEM_PROMPT = (
    "You are WUTT's clothing analysis AI. Analyze the uploaded clothing image "
    "and return a structured JSON description.\n\n"
    "You are analyzing a single clothing item photo. The photo may have "
    "imperfect lighting, casual angles, or background clutter — do your best "
    "to identify the item accurately.\n\n"
    "CATEGORY DEFINITIONS (use exactly these values):\n"
    '- "top": shirts, blouses, t-shirts, sweaters, hoodies, blazers, jackets, '
    "polos, tank tops, crop tops, cardigans\n"
    '- "bottom": pants, jeans, trousers, shorts, skirts, leggings, joggers\n'
    '- "dress": one-piece garments including maxi dress, mini dress, cocktail dress, '
    "jumpsuit, romper, gown, kaftan\n"
    '- "shoes": sneakers, heels, boots, sandals, flats, loafers, slides, flip-flops\n'
    '- "accessory": bags, belts, jewelry, scarves, hats, watches, sunglasses, gloves\n\n'
    "COLOR NAMING GUIDE (use these common fashion color names):\n"
    "- Neutrals: black, white, ivory, cream, beige, tan, brown, grey, charcoal\n"
    "- Blues: navy, royal blue, sky blue, light blue, teal, turquoise\n"
    "- Greens: olive, sage, emerald, forest green, mint, lime\n"
    "- Reds: red, burgundy, maroon, coral, rust, salmon, pink, blush, rose\n"
    "- Yellows: yellow, gold, mustard, lemon, champagne\n"
    "- Purples: purple, lavender, lilac, plum, mauve\n"
    "- Oranges: orange, peach, terracotta, bronze\n"
    "- Multiple colors: use primary color, set secondary_color for accents\n\n"
    "STYLE TAGS VOCABULARY (pick 2-4 that fit):\n"
    "minimal, classic, casual, formal, streetwear, bohemian, vintage, sporty, "
    "preppy, elegant, trendy, edgy, romantic, minimalist, chic, feminine, "
    "masculine, androgynous, ethnic, traditional, modern, retro\n\n"
    "CONFIDENCE SCORING:\n"
    "- 90-100: Clear, well-lit photo, item is unmistakable\n"
    "- 70-89: Good photo, item is clearly identifiable with minor uncertainty\n"
    "- 50-69: Decent photo, some ambiguity in type or details\n"
    "- 30-49: Poor lighting/angle, making identification harder\n"
    "- Below 30: Very blurry or unclear, mostly guessing\n\n"
    "Return ONLY a JSON object (no markdown fences, no commentary) with:\n"
    '  "category": string — one of: top, bottom, dress, shoes, accessory\n'
    '  "subtype": string — specific type, e.g. "blazer", "jeans", "maxi dress"\n'
    '  "color": string — primary color using the guide above\n'
    '  "secondary_color": string or null — secondary/accent color if visible\n'
    '  "fit": string — one of: slim, regular, oversized, relaxed\n'
    '  "style": string — style vibe, e.g. "formal", "casual", "streetwear"\n'
    '  "material_guess": string — best guess at fabric, e.g. "cotton", "silk blend"\n'
    '  "occasion_tags": array of strings — suitable occasions\n'
    '  "style_tags": array of 2-4 strings from the vocabulary above\n'
    '  "description": string — 1-2 sentence friendly description\n'
    '  "confidence": number 0-100 — how confident you are in this analysis\n'
    '  "matching_ideas": array of 2-3 strings — what to pair this with\n\n'
    "RULES:\n"
    "- Be honest about confidence — low light or blurry photos should have lower confidence.\n"
    "- For Myanmar context: note if it works with longyi, for temple, for wedding, etc.\n"
    "- Never return placeholder or fake data — only what you can see or reasonably guess.\n"
    "- Keep description natural and friendly, not robotic.\n"
    "- If you see a pattern (stripes, plaid, floral), mention it in the description.\n"
    "- Consider the item's versatility — can it be dressed up or down?"
)


def analyze_clothing_image(
    image_data: str,
    mime_type: str = "image/jpeg",
) -> dict[str, Any] | None:
    """Analyze a clothing image using Gemini Vision.

    Args:
        image_data: Base64-encoded image data (without the data:... prefix).
        mime_type: MIME type of the image (default: image/jpeg).

    Returns:
        Dict with analysis fields, or None on failure.
    """
    client = _build_client()
    if client is None:
        return None

    # Build vision prompt with knowledge context
    knowledge_snippet = ""
    if FASHION_KNOWLEDGE:
        # Include occasion rules for better matching suggestions
        occasions = FASHION_KNOWLEDGE.get("occasion_rules", {})
        if occasions:
            knowledge_snippet = (
                "\n\nContext — Myanmar occasion rules:\n"
                + json.dumps(occasions, indent=2)[:1500]
            )

    user_prompt = (
        "Analyze this clothing item photo. Look carefully at:\n"
        "1. The overall silhouette and cut to determine category and subtype\n"
        "2. The primary and any secondary colors\n"
        "3. Fabric texture and drape to guess material\n"
        "4. Any visible patterns (stripes, plaid, floral, solid)\n"
        "5. The fit (how it sits on the body or hanger)\n\n"
        "Return a JSON object with these exact fields:\n"
        "category, subtype, color, secondary_color, fit, style, material_guess, "
        "occasion_tags, style_tags, description, confidence, matching_ideas.\n\n"
        "Be specific about the subtype — 'blazer' not just 'top', 'maxi dress' "
        "not just 'dress', 'sneakers' not just 'shoes'."
        + knowledge_snippet
    )

    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=[
                _VISION_SYSTEM_PROMPT,
                gemini_types.Part.from_bytes(
                    data=image_data,
                    mime_type=mime_type,
                ),
                user_prompt,
            ],
            config=gemini_types.GenerateContentConfig(
                max_output_tokens=800,
                temperature=0.2,
            ),
        )
        raw = response.text
        if not raw:
            return None

        # Parse JSON response
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                parsed = json.loads(match.group())
            else:
                logger.error("Gemini vision returned non-JSON: %s", text[:200])
                return None

        # Normalize response
        valid_categories = {"top", "bottom", "dress", "shoes", "accessory"}
        category = parsed.get("category", "top").lower().strip()
        if category not in valid_categories:
            # Try to map common mistakes
            category_map = {
                "shirt": "top", "blouse": "top", "t-shirt": "top", "sweater": "top",
                "pants": "bottom", "jeans": "bottom", "trousers": "bottom", "skirt": "bottom",
                "gown": "dress", "jumpsuit": "dress", "romper": "dress",
                "sneaker": "shoes", "heel": "shoes", "boot": "shoes", "sandal": "shoes",
                "bag": "accessory", "belt": "accessory", "hat": "accessory", "scarf": "accessory",
            }
            category = category_map.get(category, "top")

        result = {
            "category": category,
            "subtype": parsed.get("subtype", "").strip(),
            "color": parsed.get("color", "unknown").strip(),
            "secondary_color": parsed.get("secondary_color"),
            "fit": parsed.get("fit", "regular").strip(),
            "style": parsed.get("style", "casual").strip(),
            "material_guess": parsed.get("material_guess", "").strip(),
            "occasion_tags": parsed.get("occasion_tags", []),
            "style_tags": parsed.get("style_tags", []),
            "description": parsed.get("description", "").strip(),
            "confidence": min(100, max(0, parsed.get("confidence", 70))),
            "matching_ideas": parsed.get("matching_ideas", []),
        }

        logger.info(
            "[WUTT] Vision analysis: category=%s subtype=%s color=%s confidence=%d",
            result["category"], result["subtype"], result["color"], result["confidence"],
        )
        return result

    except Exception as exc:
        cls = type(exc).__qualname__
        mod = type(exc).__module__
        logger.error("Gemini vision failed: %s.%s — %s", mod, cls, exc)
        return None
