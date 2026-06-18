# WUTT Handoff — 2026-06-17

## Current State

| Item | Status |
|------|--------|
| Backend (`wutt.onrender.com`) | ✅ Live, HTTP 200 |
| Frontend (`wutt-frontend.onrender.com`) | ✅ Live, HTTP 200 |
| Auth (register/login/JWT) | ✅ Working |
| Profile (CRUD) | ✅ Working |
| Wardrobe upload (Cloudinary) | ✅ Working (6 items) |
| Wardrobe list + delete | ✅ Working |
| Cross-user isolation | ✅ 403 enforced |
| Stylist history | ✅ Working |
| JSON stability | ✅ All responses valid JSON |
| **Stylist AI recommendation** | ⚠️ **503 — OPENAI_API_KEY missing** |

## Last Commit

```
9eb2005 fix: show real stylist error instead of generic misleading message
```

Deployed and live. Frontend now shows the actual backend error message
instead of the misleading generic "AI ဆာဗာနဲ့ချိတ်ဆက်မှုမအောင်မြင်ပါ".

## Root Cause: OPENAI_API_KEY Not Set

`backend/services/openai_svc.py:49` returns `None` because
`settings.openai_api_key` is empty. The `render.yaml` marks it
`sync: false` — it must be set manually in Render Dashboard.

The backend handles this gracefully (503 JSON error, no crash).

## Tomorrow Plan

### 1. Set OPENAI_API_KEY in Render Dashboard (P0)

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Select `wutt-api` service
3. Environment → Add environment variable:
   - Key: `OPENAI_API_KEY`
   - Value: your OpenAI API key (`sk-...`)
4. Save → Render auto-redeploys

### 2. Retest AI Stylist (P0)

After key is set:
1. Open `https://wutt-frontend.onrender.com`
2. Login with existing account (has 6 wardrobe items)
3. Enter occasion → click "AI အကြံပေး"
4. Should get structured outfit recommendation
5. If 503 persists, check Render logs for API key errors
6. If it works — run `curl -X POST /stylist/recommend` to verify JSON structure

### 3. Redesign Landing Page (P1)

Direction:
- Simpler layout, premium feel
- Myanmar-focused design language
- Avoid cluttered/generated mockups
- Clean typography, generous whitespace
- Let the product speak — not overdesigned

Files: `frontend/index.html`, `frontend/style.css`

### 4. Do Not Touch

- `backend/` — architecture frozen
- Auth system — working, don't refactor
- Database schema — stable
- `render.yaml` — deployment config is correct
- `.env` — never commit, never edit

## Quick Test Commands

```bash
# Health check
curl https://wutt.onrender.com/health

# Stylist test (once key is set)
curl -X POST https://wutt.onrender.com/stylist/recommend \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"occasion":"wedding"}'

# Run in frontend dev
cd frontend && python3 -m http.server 3000

# Run backend locally with .env
cd backend && uvicorn main:app --reload --port 8000
```
