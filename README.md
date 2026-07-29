# WUTT — AI Fashion Companion

<p align="center">

## Know Your Wardrobe. Upgrade Your Style.

</p>

WUTT is an AI-powered personal fashion companion that helps users organize their wardrobe, understand their clothing, and receive personalized outfit recommendations.

Instead of wondering:

> "What should I wear today?"

WUTT helps users discover better outfit choices based on their wardrobe, occasions, and personal style.

---

# ✨ Features

## 👕 Digital Wardrobe

Create your personal digital closet.

Users can:

- Upload clothing images
- Organize wardrobe items
- Save clothing collections
- Manage personal wardrobe items

Each wardrobe item can contain:

- Category
- Subcategory
- Color
- Description
- Style tags
- Occasion tags

---

## 💬 AI Stylist Assistant

Chat with WUTT AI for personalized fashion guidance.

Users can ask:

- "What should I wear for a date?"
- "How can I style this outfit?"
- "What matches with my wardrobe?"

WUTT provides suggestions based on:

- Occasion
- Personal style
- Existing wardrobe items
- Fashion context

---

## 👤 Personal Style Profile

Create your own fashion identity.

Users can customize:

- Personal information
- Style preferences
- Fashion interests

This creates a more personalized styling experience.

---

# 🧠 How WUTT Works

```text
Add Clothing Items
|
↓
Review & Organize Wardrobe
|
↓
Digital Closet
|
↓
AI Stylist Conversation
|
↓
Personalized Outfit Suggestions
```  

---

# 🛠 Technology Stack

## Frontend

- HTML
- CSS
- JavaScript
- Responsive UI architecture

## Backend

- Python
- FastAPI
- SQLAlchemy
- SQLite (MVP)

## AI Integration

### AI Chat

- OpenRouter
- OpenAI-compatible API

### Future AI Vision Enhancement

- Google Gemini Vision integration planned for future wardrobe automation improvements

## Deployment

- Frontend: Render
- Backend: Render

---

# 🤖 AI-Assisted Development

WUTT was developed using an AI-assisted engineering workflow.

## Tools Used

- Claude Code
- UI Reviewer Agent
- WUTT UI Review Skill

## Development Workflow


Analyze Problem
|
↓
Design Solution
|
↓
Implement Changes
|
↓
Review & Test
|
↓
Improve Experience


AI was used for:

- Code analysis
- Debugging
- UI review
- Development workflow support

---

# 📸 Screenshots

## Landing Experience

![Landing](screenshots/landing.png)

---

## AI Stylist Chat

![AI Stylist](screenshots/aistylistchat.png)

---

## Digital Wardrobe

![Wardrobe](screenshots/wardrobe.png)

---

# 🚀 Local Development

## Backend Setup

```bash
cd backend

pip install -r requirements.txt

uvicorn main:app --reload --port 8000

Backend runs at:

http://localhost:8000

## Frontend Setup

```bash
cd frontend

python3 -m http.server 5500

Open:

http://localhost:5500
🔐 Environment Configuration

Create your local environment file:

cp .env.example backend/.env

Example:

DATABASE_URL=sqlite:///./wutt.db

JWT_SECRET_KEY=your-secret-key

OPENROUTER_API_KEY=your-api-key

GEMINI_API_KEY=your-api-key

Never commit secret keys into the repository.

🎯 Demo Experience

WUTT includes a dedicated demo login flow for testing and presentation.

Demo users can explore:

AI Stylist experience
Wardrobe management
Personal style features
🌐 Live Demo

Frontend:

https://wutt-frontend.onrender.com/



📂 Project Structure
```text
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
└── LICENSE

## 🌱 Future Improvements

Future versions of WUTT may include:


## Smarter Fashion Intelligence

- More accurate AI outfit recommendations
- Weather-based outfit suggestions
- Better personal style understanding

## Advanced Wardrobe Features

- Automatic clothing recognition
- Advanced wardrobe analytics
- Outfit history tracking
- Smart wardrobe organization

## New Experiences

- Virtual try-on experience
- Mobile application support
- Shopping assistant features
- Social style sharing

📄 License

This project is licensed under the MIT License.

👨‍💻 Creator

Tain Sin Moe

GitHub:

https://github.com/tainsinmoe04/wutt