# WUTT — AI Fashion Companion

**"Know Your Wardrobe. Upgrade Your Style."**

Upload your wardrobe. Pick an occasion. Get an outfit recommendation that fits the weather and your style.

![Landing Page](screenshots/landing.png)

---

## What It Does

1. Upload wardrobe items — photos stored on Cloudinary, categorised by type and colour
2. Set your profile — height, skin tone, style preference, city
3. Choose an occasion — wedding, party, interview, casual, temple, date, work, sport
4. Get a recommendation — complete outfit with explanation and weather-based styling tip

The recommendation engine is rule-based — it classifies items, scores them against occasion and weather, and assembles valid outfits. Works without any API keys.

### Phase 2 — Current Focus

- **AI Chat** — conversational styling assistant powered by Gemini Vision
- **Gemini Vision** — outfit analysis, wardrobe item recognition, style advice
- **Wardrobe flow** — upload, categorise, and manage your wardrobe items

### Coming Soon (Locked)

- **Shop/Seller integration** — browse and purchase recommended items
- **Virtual try-on / MR** — see how outfits look before buying (future phase)

---

## Screenshots

| Stylist | Wardrobe |
|---------|----------|
| ![Dashboard](screenshots/dashboard-stylist.png) | ![Wardrobe](screenshots/wardrobe-grid.png) |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML + CSS (BEM, CSS variables) + JavaScript |
| Backend | Python FastAPI + SQLAlchemy + SQLite |
| AI Vision | Google Gemini Vision (outfit analysis, wardrobe recognition) |
| Images | Cloudinary (server-side signed uploads) |
| Font | Space Grotesk via Google Fonts |
| Deploy | Render.com |

OpenAI GPT-4o Vision and OpenWeatherMap are optional — the app works without them.

---

## Setup

```
# Backend
cd backend && pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend
cd frontend && python -m http.server 3000

# Health check
curl http://localhost:8000/health
```

### Environment Variables

```
DATABASE_URL=sqlite:///./wutt.db
JWT_SECRET_KEY=<random string>
CLOUDINARY_CLOUD_NAME=<required>
CLOUDINARY_API_KEY=<required>
CLOUDINARY_API_SECRET=<required>
GEMINI_API_KEY=<optional>
OPENAI_API_KEY=<optional>
WEATHER_API_KEY=<optional>
```

---

## Project Structure

```
frontend/          Landing page, dashboard, design system
backend/           FastAPI API — auth, profile, wardrobe, stylist routes
slides/            Presentation deck (Marp)
report.md          Class submission report
```

---

## Design System

```
Primary:   #88A2FF    Deep:    #253A82
Energy:    #E3FC87    Blush:   #FFB2F7
Sky:       #C0E0FF    Lavender: #AB9DFF
```

Font: **Space Grotesk** (300–700)

---

**Tain Sin Moe** — [github.com/tainsinmoe04/wutt](https://github.com/tainsinmoe04/wutt)
