# WUTT — AI Fashion Companion

<p align="center">

**Know Your Wardrobe. Upgrade Your Style.**

</p>

WUTT is an AI-powered personal fashion companion that helps users organize their wardrobe, understand their clothing, and receive personalized outfit recommendations.

Instead of wondering *"What should I wear today?"*, users can build their digital wardrobe and get styling guidance based on their own clothes, occasion, and personal preferences.

---

# ✨ Features

## 👕 Digital Wardrobe

Build your personal digital closet.

- Upload clothing images
- Organize wardrobe items
- View saved clothing collections
- Manage your wardrobe easily

---

## 🤖 AI Clothing Analysis

WUTT uses AI vision technology to understand clothing images.

The AI can analyze:

- Clothing category
- Clothing type
- Primary color
- Style
- Fit
- Material estimation
- Fashion tags

Example:

```
Upload shirt image

↓

AI analyzes clothing

↓

Save item into wardrobe
```

---

## 💬 AI Stylist Assistant

Chat with WUTT AI for personalized fashion advice.

Users can ask:

- "What should I wear for a date?"
- "How can I style this outfit?"
- "What matches with my wardrobe?"

WUTT provides suggestions based on:

- Occasion
- Personal style
- Wardrobe items
- Fashion context

---

## 👤 Personal Style Profile

Create a personal fashion profile.

Users can customize:

- Personal information
- Style preferences
- Fashion identity

---

# 🧠 How WUTT Works

```
Upload Clothing
        |
        ↓
AI Clothing Analysis
        |
        ↓
Digital Wardrobe
        |
        ↓
AI Stylist Conversation
        |
        ↓
Personalized Outfit Suggestions
```

---

# 🛠 Tech Stack

## Frontend

- HTML
- CSS
- JavaScript

## Backend

- Python
- FastAPI
- SQLAlchemy
- SQLite

## Artificial Intelligence

### AI Chat

- OpenRouter
- OpenAI-compatible API

### AI Vision

- Google Gemini Vision

---

# 📸 Screenshots

## Landing Page

![Landing](screenshots/landing.png)

## Wardrobe

![Wardrobe](screenshots/wardrobe-grid.png)

## AI Stylist

![Stylist](screenshots/dashboard-stylist.png)

---

# 🚀 Local Development

## Backend

```bash
cd backend

pip install -r requirements.txt

uvicorn main:app --reload --port 8000
```

Backend runs at:

```
http://localhost:8000
```

---

## Frontend

```bash
cd frontend

python3 -m http.server 5500
```

Open:

```
http://localhost:5500
```

---

# 🔐 Environment Variables

Create a `.env` file inside backend:

```env
DATABASE_URL=sqlite:///./wutt.db

OPENROUTER_API_KEY=your_api_key

OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

OPENROUTER_AI_MODEL=openai/gpt-oss-20b:free

GEMINI_API_KEY=your_api_key
```

---

# 📂 Project Structure

```
wutt/

├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
│
├── backend/
│   ├── main.py
│   ├── routes/
│   ├── services/
│   └── models.py
│
├── screenshots/
│
├── slides/
│
├── report.md
│
└── LICENSE
```

---

# 🌱 Future Improvements

Future versions of WUTT may include:

- Smarter outfit planning
- Fashion recommendation history
- Shopping assistant
- Virtual try-on experience
- Advanced personal style memory

---

# 📄 License

This project is licensed under the MIT License.

---

# 👨‍💻 Creator

**Tain Sin Moe**

GitHub:

https://github.com/tainsinmoe04/wutt