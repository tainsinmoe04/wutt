# Skill: WUTT AI Outfit Recommendation Logic

## When to use this skill
Load this skill when working on: stylist.py, OpenAI prompt engineering, outfit recommendation features.

## OpenAI Vision API — WUTT Prompt Template
```python
SYSTEM_PROMPT = """
You are WUTT, Myanmar's AI Personal Stylist.
You analyze wardrobe photos and give outfit recommendations.

Rules:
- Respond in Myanmar (Burmese) language
- Consider: occasion, weather, temperature, body proportions
- Be specific: name exact items from uploaded photos
- Give 1 primary outfit + 1 backup option
- Include: what to wear, how to style, what accessories
- Keep advice practical and culturally appropriate for Myanmar

Response format (JSON):
{
  "primary_outfit": {
    "items": ["item1", "item2"],
    "styling_tips": "...",
    "accessories": "..."
  },
  "backup_outfit": {
    "items": ["item1", "item2"],
    "styling_tips": "..."
  },
  "weather_note": "...",
  "occasion_note": "..."
}
"""

USER_PROMPT_TEMPLATE = """
Occasion: {occasion}
Weather: {weather_desc}, {temperature}°C
Location: {location}
User height: {height}cm

Please analyze the wardrobe photos and recommend the best outfit.
"""
```

## Occasion Categories (Myanmar Language)
```python
OCCASIONS = [
    "မင်္ဂလာပွဲ",      # Wedding
    "ရုံးသွားမယ်",      # Office/Work
    "ပါတီ/ဆေးဆုံ",     # Party
    "နေ့စဉ်ဝတ်",       # Casual daily
    "ရုပ်ရှင်/မားလ်",  # Date/Mall
    "ဘုရားသွားမယ်",    # Religious
    "အင်တာဗျူး",       # Interview
    "အပြင်ထွက်",       # Outdoor
]
```

## Image Handling
```python
import base64

def encode_image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def build_vision_messages(images: list[str], occasion: str, weather: dict, height: int):
    content = [{"type": "text", "text": USER_PROMPT_TEMPLATE.format(
        occasion=occasion,
        weather_desc=weather["description"],
        temperature=weather["temp"],
        location=weather["city"],
        height=height
    )}]

    for img_url in images:
        content.append({
            "type": "image_url",
            "image_url": {"url": img_url, "detail": "high"}
        })

    return [{"role": "user", "content": content}]
```

## Error Handling for AI responses
- If OpenAI returns non-JSON: wrap in try/except, return fallback message in Myanmar
- If no wardrobe images: prompt user to upload at least 2 photos
- If weather API fails: ask user to input weather manually
