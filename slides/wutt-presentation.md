---
marp: true
theme: default
paginate: true
backgroundColor: #0A0A0A
color: #FFFFFF
style: |
  section {
    font-family: 'Space Grotesk', 'Segoe UI', sans-serif;
    padding: 40px 60px;
  }
  h1 { color: #88A2FF; font-size: 2.4em; margin-bottom: 0.3em; }
  h2 { color: #E3FC87; font-size: 1.8em; margin-bottom: 0.4em; }
  h3 { color: #C0E0FF; }
  strong { color: #FFB2F7; }
  ul { font-size: 1.2em; line-height: 1.8; }
  li { margin-bottom: 0.3em; }
  a { color: #AB9DFF; }
  .small { font-size: 0.85em; color: #999; }
  .tag { display: inline-block; background: #253A82; color: #C0E0FF; padding: 2px 12px; border-radius: 20px; font-size: 0.8em; margin: 4px; }
---

<!-- _class: lead -->

# WUTT
## AI Personal Stylist for Myanmar

**"ဒီနေ့ ဘာဝတ်ရမလဲ?"**

*What should I wear today?*

<div class="small">Tain Sin Moe · June 2026</div>

---

<!-- _header: "The Problem" -->

## 👗 Every Morning, Same Question

<br>

- **Decision fatigue** — staring at a full wardrobe with "nothing to wear"
- **Myanmar weather** — 35°C and humid vs. sudden rain vs. air-conditioned indoors
- **Occasion confusion** — is this outfit right for a wedding? Pagoda visit? Office?
- **Color coordination** — matching skin tone, occasion, and cultural norms
- **No local solution** — existing apps don't understand Myanmar fashion, longyi, or culture

<br>

<div class="small">Millions of Myanmar youth own smartphones. Zero AI stylists speak their context.</div>

---

<!-- _header: "The Solution" -->

## 🤖 AI That Understands Myanmar

<br>

1. **📸 Upload your wardrobe** — photos go to Cloudinary
2. **📝 Tell us the occasion** — wedding, work, party, date, Thingyan...
3. **🌤️ Real weather data** — Yangon rain? Mandalay heat? We know.
4. **🧠 GPT-4o Vision** — analyzes each garment visually
5. **✨ Get a recommendation** — complete outfit with reasoning

<br>

> *"Pair your navy longyi with the white mandarin-collar shirt. The blue complements medium skin tone perfectly. Cotton breathes well in 33°C Yangon humidity."*

---

<!-- _header: "Tech Stack" -->

## ⚙️ Built With

| Layer | Technology |
|-------|-----------|
| **Frontend** | Vanilla HTML + CSS + JavaScript, BEM design system |
| **Backend** | Python FastAPI, SQLAlchemy 2.0 ORM |
| **Database** | SQLite (MVP) → PostgreSQL |
| **AI Engine** | OpenAI GPT-4o Vision API |
| **Images** | Cloudinary (server-side signed uploads) |
| **Weather** | OpenWeatherMap API (graceful degradation) |
| **Auth** | JWT via httpOnly cookies, bcrypt hashing |
| **Deploy** | Render.com (web service + static site) |

<div class="small">WUTT Design System: #88A2FF primary · #253A82 deep · #E3FC87 energy · Space Grotesk font</div>

---

<!-- _header: "Key Features" -->

## ✨ What WUTT Does

<div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:20px;">

<div>

### 👤 Smart Profile
- Height, skin tone, style preference
- City-based auto weather
- Partial updates supported

### 👔 Wardrobe Manager
- Upload JPEG/PNG/WebP
- Categorize by type & color
- Cloudinary secure storage

</div>

<div>

### 🎯 AI Stylist
- Occasion-aware recommendations
- Color/skin tone matching
- Weather-appropriate picks
- Myanmar cultural sensitivity

### 🔒 Security First
- bcrypt passwords
- httpOnly JWT cookies
- Ownership checks on all data

</div>

</div>

---

<!-- _class: lead -->

# 🚀 Try It Live

<br>

### 🔗 **https://wutt.onrender.com**

<br>

### 📂 GitHub
### **github.com/tainsinmoe04/wutt**

<br>

<div style="display:flex;gap:10px;justify-content:center;margin-top:30px;">
<span class="tag">FastAPI</span>
<span class="tag">OpenAI Vision</span>
<span class="tag">Cloudinary</span>
<span class="tag">Myanmar 🇲🇲</span>
</div>

<br>

## ✨ ကျေးဇူးတင်ပါတယ် — Thank You!
