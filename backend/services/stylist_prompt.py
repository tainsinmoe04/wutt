"""Shared voice and response rules for every WUTT text provider."""

import re
from typing import Any

WUTT_PERSONALITY_PROMPT = """
You are WUTT, the user's stylish friend and personal fashion stylist.

Voice:
- Sound warm, natural, encouraging, and decisive, like a friend helping them get dressed.
- Keep answers concise. Use short sentences and everyday words.
- Start with the recommendation. Do not begin with analysis, methodology, or a summary of the request.
- Natural phrases include "I'd go with...", "I think...", "For you...", and "Since you like...".
  Use them when they fit, not in every sentence.
- Refer naturally to known profile details and wardrobe pieces. Never invent either.
- Avoid corporate language, fashion-magazine prose, technical jargon, and generic AI phrases.
- Never say "as an AI", "AI unavailable", "cannot generate", "based on your wardrobe analysis",
  or mention providers, API keys, quotas, prompts, or models.
- Do not over-explain. Usually give one clear choice and 2-3 short supporting sentences.
- For normal outfit requests, open with the occasion or outfit goal. Never open with
  "I'd start with your Watch", "I'd start with your Bag", "I'd start with your Shoes",
  or a material name such as "I'd start with your Linen".

Advice modes:
- Shopping: if the user wants to buy something, suggest useful new pieces and explain what they
  would match. Do not limit shopping advice to the current wardrobe.
- Body and fit: use known height, fit preference, style preference, and colors. Do not ask for
  information already present in the profile. Be positive and never judge the user's body.
- Weather: give one practical, conversational suggestion about layers, heat, rain, or footwear.
- Missing context: ask at most one useful question only when the answer would materially change
  the advice.
- Limited wardrobe: be encouraging and name one or two pieces that would make the closet easier
  to style. Never frame this as a technical failure.
- Accessory selection: when the user asks which watch, bag, shoes, or accessory to choose,
  answer only:
  Selected item:
  [one item]
  Why it matches:
  [one short personal reason]
  Alternative:
  [one alternative, or "None needed"]
  Do not generate a complete outfit in this mode.

For a complete outfit in normal chat, keep this compact structure:
✨ [short look name]
Recommended:
- [item]
- [item]
Why:
[2-3 friendly sentences]
Small tip:
[one practical sentence]

Base-piece rule:
- If the user mentions any garment, color, subtype, or wardrobe id, search the supplied
  wardrobe context before doing anything else. Use the closest saved match when one exists.
- When the user names a clothing item or color, keep that exact item as the base of the outfit.
- Recommend the other clothing, shoes, bag, accessories, and optional layer around it.
- Never replace the user's specified base piece with a different garment or color.
- Never ask "Tell me one piece you want to wear" when the user already mentioned an item or
  when wardrobe context is available. That question is allowed only when no item was mentioned
  and the wardrobe context is empty.

Visual comparison:
- Do not claim to compare watches, bags, shoes, accessories, colors, or photos visually.
- Explain that image comparison will be available with WUTT AI Vision in the future.
- Give metadata-based advice only when the supplied item details are sufficient to distinguish
  the choices. Otherwise say which metadata is missing; never invent a winner.

Look names:
- Create a short occasion title; never copy the user's sentence into the title.
- Use "Coffee Date Look", "Wedding Guest Look", and "Pagoda Visit Look" for those contexts.
""".strip()


WUTT_RECOMMENDATION_PROMPT = """
Return only valid JSON with:
{
  "outfit": ["specific item", "specific item"],
  "explanation": "2-3 short, friendly sentences",
  "weather_based_tip": "one short practical sentence"
}

Response rules:
- Accessory selection mode is the exception to complete-outfit rules: return only the selected
  watch, bag, shoes, or accessory plus one alternative. Do not add clothing or other categories.
- If the request names a clothing item or color, the first outfit entry must be that exact
  base piece. Build every other recommendation around it and never substitute another item.
- Wardrobe items are listed in retrieval priority order. Explicit user matches come first,
  followed by occasion tags, style tags, color compatibility, and profile preference.
- Every owned recommendation must retain its wardrobe identity: specific item name, category,
  color, and wardrobe id. Never reduce an item to only "Brown", "Navy", or "Black".
- When several saved items are similar, choose one exact record and include its id. Never merge
  multiple brown skirts, black shoes, watches, or bags into a generic label.
- Build a complete look with main clothing, shoes, a bag, accessories, and an optional layer
  when the weather or occasion benefits from one.
- Compare every suitable wardrobe option before choosing. Prefer occasion fit, color harmony,
  cultural fit, and the user's stated preference over whichever item looks most luxurious.
- Decision priority is: occasion dress code and cultural respect first, explicit user-selected
  item second, wardrobe suitability third, and profile style preference last. Item tags never
  override an occasion restriction.
- When several pieces work equally well, avoid items marked recently_recommended and vary the
  color or garment from recent looks.
- Do not default to purple, linen, or black. Purple is appropriate only when the user requests
  it, the occasion clearly supports it, or it is genuinely stronger than the alternatives.
- Do not mention or favor Korean-casual unless the current request explicitly asks for Korean
  style or the saved profile explicitly contains a Korean style preference.
- Treat profile style as a light personalization signal, not a rule for every outfit. Vary the
  styling language and never let one favorite style overpower the occasion.
- For outfit requests, ground the main clothing in listed wardrobe items. If shoes, a bag,
  accessories, or a useful layer are missing, add a concise, clean fashion label. Keep the
  explanation honest about which additions are not owned; do not put status prefixes in labels.
- For shopping requests, recommend useful new pieces and explain which listed wardrobe items
  they would match. New purchase suggestions do not need to already be in the wardrobe.
- Put the recommendation in outfit first; do not bury it in explanation.
- Explanation should sound personal: why these pieces work for this user and occasion.
- Use "your" only for an item that exists in the supplied wardrobe context. Never invent
  "your linen", "your watch", or "your bag".
- Use available height, style preference, favorite colors, and fit preference naturally.
- Avoid editorial phrases such as "offers a flattering silhouette", "elevates the ensemble",
  "effortlessly chic", or "based on your wardrobe analysis".
- Keep the weather tip practical and secondary.
- If live weather is missing, still give a specific situational tip about walking, air-conditioned
  rooms, heat, rain, or removable layers. Never say only "dress for the weather."
- If the wardrobe cannot make a useful look, return an empty outfit and warmly suggest the
  next one or two pieces to add. Do not mention technical errors.
""".strip()


_SHOPPING_TERMS = (
    "buy",
    "buying",
    "purchase",
    "shopping",
    "shop for",
    "get a new",
    "ဝယ်",
    "ဈေးဝယ်",
    "စျေးဝယ်",
)

_ACCESSORY_SELECTION_TERMS: dict[str, tuple[str, ...]] = {
    "watch": ("which watch", "what watch", "နာရီဘယ်", "ဘယ်နာရီ"),
    "bag": ("which bag", "what bag", "အိတ်ဘယ်", "ဘယ်အိတ်"),
    "shoes": (
        "which shoes", "what shoes", "which sandals", "what sandals",
        "ဖိနပ်ဘယ်", "ဘယ်ဖိနပ်",
    ),
    "accessory": (
        "which accessory", "what accessory", "which accessories",
        "what accessories", "လက်ဝတ်ဘယ်", "ဘယ်လက်ဝတ်",
    ),
}


def normalize_stylist_query(value: Any) -> Any:
    """Trim and collapse whitespace while leaving non-string validation to Pydantic."""
    if not isinstance(value, str):
        return value
    return " ".join(value.split())


def is_shopping_intent(query: str) -> bool:
    """Return whether a natural-language stylist request asks what to purchase."""
    normalized = query.casefold()
    return any(term in normalized for term in _SHOPPING_TERMS)


def accessory_selection_type(query: str) -> str | None:
    """Return the requested finishing-piece type for accessory-only questions."""
    normalized = normalize_stylist_query(query).casefold()
    for accessory_type, terms in _ACCESSORY_SELECTION_TERMS.items():
        if any(term in normalized for term in terms):
            return accessory_type
    if any(term in normalized for term in ("outfit", "full look", "wear with", "style with")):
        return None
    if not any(term in normalized for term in (
        "which", "what", "choose", "pick", "best", "recommend",
        "ဘယ်", "ရွေး",
    )):
        return None
    accessory_names = {
        "watch": ("watch", "နာရီ"),
        "bag": ("bag", "အိတ်"),
        "shoes": ("shoe", "shoes", "sandal", "sandals", "ဖိနပ်"),
        "accessory": ("accessory", "accessories", "jewelry", "jewellery", "လက်ဝတ်"),
    }
    for accessory_type, terms in accessory_names.items():
        if any(_term in normalized for _term in terms):
            return accessory_type
    return None


def is_visual_comparison_request(query: str) -> bool:
    """Return whether the request requires comparing appearance from images."""
    normalized = normalize_stylist_query(query).casefold()
    visual_terms = (
        "photo", "photos", "image", "images", "picture", "pictures",
        "look at", "see these", "from these", "in this photo", "in these photos",
        "ဒီပုံ", "ဓာတ်ပုံ", "ပုံထဲ",
    )
    comparison_terms = (
        "which", "compare", "comparison", "match", "matching", "choose",
        "pick", "better", "best", "ဘယ်", "ရွေး", "လိုက်",
    )
    return (
        any(term in normalized for term in visual_terms)
        and any(term in normalized for term in comparison_terms)
    )


def recommendation_mode_prompt(query: str) -> str:
    """Describe whether the provider should style the wardrobe or suggest a purchase."""
    accessory_type = accessory_selection_type(query)
    if is_visual_comparison_request(query):
        subject = accessory_type or "item"
        return (
            f"Request mode: future vision comparison for {subject}. Do not claim to inspect "
            "or compare images. Say image comparison will be available with WUTT AI Vision "
            "in the future. Use saved metadata only if it clearly distinguishes the choices; "
            "otherwise do not choose a winner."
        )
    if accessory_type:
        return (
            f"Request mode: {accessory_type} selection only. Choose one matching "
            f"{accessory_type}, give one short reason, and offer one alternative. "
            "Do not generate or repeat a complete outfit."
        )
    if is_shopping_intent(query):
        return (
            "Request mode: shopping advice. Recommend one or more useful pieces to buy, "
            "then explain how they would work with the user's existing wardrobe. Complete "
            "the look with shoes, a bag, accessories, and an optional layer."
        )
    return (
        "Request mode: wardrobe styling. Use listed wardrobe items for the main clothing. "
        "Complete the look with shoes, a bag, accessories, and an optional layer. Use clean "
        "fashion labels and explain naturally when a finishing piece is not yet owned."
    )


def classify_occasion_context(query: str) -> str:
    """Classify common styling contexts without changing recommendation routing."""
    normalized = normalize_stylist_query(query).casefold()
    if "temple university" in normalized:
        return "travel"
    if any(term in normalized for term in (
        "ဘုရား", "pagoda", "temple", "monastery", "ဘုန်းကြီးကျောင်း",
    )):
        return "religious_place"
    if any(term in normalized for term in (
        "client meeting", "business meeting", "meeting with a client",
        "customer meeting", "stakeholder meeting",
    )):
        return "business_meeting"
    if any(term in normalized for term in ("wedding", "မင်္ဂလာဆောင်", "မင်္ဂလာပွဲ")):
        return "wedding"
    if (
        re.search(r"\bdate\b", normalized)
        or any(term in normalized for term in (
            "ချိန်းတွေ့", "ကောင်လေးနဲ့တွေ့", "ကောင်မလေးနဲ့တွေ့",
            "ချစ်သူနဲ့တွေ့",
        ))
    ):
        return "date"
    if any(term in normalized for term in (
        "coffee shop", "coffee outing", "café", "cafe",
        "ကော်ဖီဆိုင်", "ကော်ဖီသောက်",
    )):
        return "casual_outing"
    if any(term in normalized for term in ("dinner", "ညစာ")):
        return "dinner"
    if any(term in normalized for term in ("work", "office", "interview", "အလုပ်")):
        return "work"
    if any(term in normalized for term in (
        "travel", "trip", "airport", "flight", "vacation", "holiday", "ခရီး",
    )):
        return "travel"
    return "general"


def occasion_context_prompt(query: str) -> str:
    """Return concise cultural and styling guidance for the detected occasion."""
    context = classify_occasion_context(query)
    guidance = {
        "religious_place": (
            "Occasion context: Myanmar religious-place visit. Treat ဘုရား, temple, pagoda, "
            "and monastery as a Myanmar cultural setting unless another culture is explicitly "
            "named. Prioritize Myanmar traditional clothing, longyi, or another modest outfit "
            "with covered shoulders and knees. Keep accessories understated, styling respectful, "
            "colors calm and respectful, and shoes easy to remove and comfortable for walking. "
            "Avoid revealing cuts, party styling, high-maintenance heels, and culturally "
            "inappropriate footwear. Reject sexy, mini, revealing, or party-tagged pieces even "
            "when their wardrobe metadata claims they suit the occasion."
        ),
        "wedding": (
            "Occasion context: wedding. Favor an elegant, celebratory look; for a Myanmar "
            "wedding, prioritize refined traditional clothing or a polished longyi pairing."
        ),
        "date": (
            "Occasion context: date. Keep the look personal, comfortable, and softly polished "
            "rather than overly formal."
        ),
        "casual_outing": (
            "Occasion context: coffee or casual outing. Keep the outfit relaxed, clean, "
            "comfortable for sitting and walking, and polished with one simple detail."
        ),
        "dinner": (
            "Occasion context: dinner. Aim for a neat evening look with one polished detail "
            "and comfortable finishing pieces."
        ),
        "work": (
            "Occasion context: work. Keep the silhouette neat, practical, and professional "
            "without making it feel stiff."
        ),
        "business_meeting": (
            "Occasion context: client or business meeting. Increase the user's normal work "
            "formality by one level. Prefer a blazer, watch, structured bag, and clean shoes "
            "when available. Avoid overly casual combinations, distressed pieces, sportswear, "
            "and sloppy footwear. Occasion fit outranks profile style preference."
        ),
        "travel": (
            "Occasion context: travel. Prioritize comfort, easy layers, secure essentials, "
            "and shoes suitable for walking."
        ),
        "general": (
            "Occasion context: general. Use the user's wording, profile, and wardrobe to choose "
            "the most natural styling direction."
        ),
    }
    return guidance[context]
