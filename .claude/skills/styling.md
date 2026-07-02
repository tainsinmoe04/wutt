# Skill: WUTT Fashion Intelligence

## When to use

Load when working on: stylist.py, outfit recommendations, wardrobe classification, occasion matching, fashion-related frontend features.

## Core Concept

WUTT's recommendation engine is rule-based metadata matching. The fallback system in `backend/routes/stylist.py` is the primary working recommendation path. OpenAI Vision is optional and unverified — the app works without it.

## Occasion Categories

| Key | Myanmar | English |
|-----|---------|---------|
| wedding | မင်္ဂလာပွဲ | Wedding |
| work | ရုံးသွား | Office/Work |
| party | ပါတီ | Party |
| date | ချိန်းတွေ့ | Date |
| casual | အပြင်ထွက် | Casual daily |
| interview | အင်တာဗျူး | Interview |
| sport | အားကစား | Sport |
| temple | ဘုရားဖူး | Religious/Temple |

## Item Classification

WUTT classifies wardrobe items into 7 types using category → subtype → description, in that priority order:

| Type | Keywords |
|------|----------|
| dress | dress, gown, jumpsuit, one-piece, ဂါဝန် |
| top | shirt, blouse, t-shirt, sweater, hoodie, blazer, အင်္ကျီ |
| bottom | trouser, pant, jeans, short, skirt, ဘောင်းဘီ, လုံချည် |
| traditional | longyi, htamein, taikpon, မြန်မာ, ရိုးရာ |
| outerwear | coat, cardigan, shawl, jacket, အင်္ကျီအပေါ်ခံ |
| accessory | bag, belt, jewelry, scarf, hat |
| shoes | sandal, heel, ဖိနပ် |

## Outfit Composition Rules

**Valid combinations:**
- One dress only
- One top + one bottom
- One traditional/formal set
- Any of the above + one outerwear or accessory (optional)

**Invalid — never generate:**
- dress + dress
- top + top
- bottom + bottom
- dress + top + bottom

## Occasion-Specific Rules

### Interview
- Prefer navy, white, beige, black, gray colours
- Avoid bright yellow/orange
- No mini skirts
- Formal dress or top+bottom combo

### Wedding
- Prefer traditional/longyi set or formal dress
- Wedding colours: red, gold, pink, purple, navy, green, cream
- Avoid casual top+bottom
- If no wedding item exists, say so honestly

### Party
- Prefer party dress or bold colours (red, black, gold)
- Mini skirt and mini dress are acceptable
- Bright accent colours welcome
- Fallback: blouse + skirt over t-shirt + jeans

### Casual
- Prefer comfortable top+bottom combos (blouse+jeans, t-shirt+skirt)
- Light colours for hot weather
- Optional outerwear (jean coat, jacket)
- Dress is fallback if no top+bottom exists

### Generic (work, date, sport, temple)
- Preference order: traditional > dress > top+bottom
- If only one category available, use it with honest limitation note

## Colour Matching Sets

| Occasion | Preferred Colours |
|----------|------------------|
| Party | red, black, gold, silver, purple, pink, white |
| Interview | navy, white, beige, black, gray |
| Wedding | red, gold, pink, purple, navy, green, cream |
| Bright accents | yellow, orange, neon (party/casual only) |

## Scoring System

Each item is scored 0–100 on these dimensions:

1. **Occasion-category fit** — does the item type suit the occasion? (with subtype bonus/penalty)
2. **Colour discipline** — does the colour match occasion-appropriate sets?
3. **Style preference alignment** — small bonus if matches user's style preference
4. **Weather suitability** — penalize heavy fabrics in hot weather
5. **Description quality** — items with descriptions score slightly higher

When multiple items share the top score (within 5 points), one is picked at random for variety.

## Weather Tips

| Condition | Tip (Myanmar) |
|-----------|---------------|
| Hot (>32°C) | ရာသီဥတုပူလို့ ပေါ့ပါးပြီး လေဝင်လေထွက်ကောင်းတဲ့အဝတ်ကို ရွေးပါ |
| Rain | မိုးရွာနိုင်လို့ ထီးယူဖို့ မမေ့ပါနဲ့ |
| Cool (<20°C) | အေးနေလို့ အပေါ်ထပ်တစ်ခု ထပ်ဆောင်းသွားပါ |
| Humid | စိုစွတ်နေလို့ ချွေးစုပ်တဲ့အထည်တွေ ရွေးပါ |

## Response Format

```json
{
  "outfit": ["item1 label", "item2 label"],
  "explanation": "why this outfit works for the occasion",
  "weather_based_tip": "practical weather advice in Myanmar"
}
```

The `source` field in the API response indicates whether the recommendation came from `"ai"` or `"fallback"`.

## Myanmar Item Labels

Items are labelled using subtype-specific Myanmar translations when available, falling back to category labels. Examples:

| Subtype | Label |
|---------|-------|
| blouse | blouse / ဘလောက်စ် |
| jeans | jeans / ဂျင်းဘောင်းဘီ |
| party dress | ပွဲတက်ဂါဝန် |
| longyi | လုံချည် |
| mini skirt | mini skirt / စကတ်တို |

Labels append colour and description when available: `blouse / ဘလောက်စ် · white — office wear`

## OpenAI Vision (Optional, Unverified)

OpenAI Vision is a secondary recommendation path. On any error or missing API key, the system falls back to the rule-based engine automatically.

- Sends metadata dicts (url, category, subtype, color, description, style_tags, occasion_tags) — not base64
- Uses Cloudinary image URLs
- Missing `OPENAI_API_KEY` → graceful 503 → fallback
- Never assume Vision is working without testing
