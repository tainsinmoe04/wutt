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

## ✏️ Manual Wardrobe Details

For the current MVP, users review wardrobe information themselves after
choosing a clothing image:

- Clothing category and subtype
- Color and description
- Style tags
- Occasion tags

Example:

```
Upload shirt image

↓

Review and edit clothing details

↓

Save item into wardrobe
```

Gemini Vision remains in the backend as a future enhancement, but wardrobe
creation does not depend on AI analysis.

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

| ![Wardrobe](screenshots/wardrobe.png)

## AI Stylist

| ![Profile](screenshots/profile.png)

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

Copy the environment template into the backend directory:

```bash
cp .env.example backend/.env
```

Then update `backend/.env` with your local values:

```env
DEBUG=true
FRONTEND_URL=http://localhost:5500
DATABASE_URL=sqlite:///./wutt.db
JWT_SECRET_KEY=generate-a-random-local-secret

GOOGLE_CLIENT_ID=your-google-web-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-web-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

OPENROUTER_API_KEY=your_api_key

OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

OPENROUTER_AI_MODEL=openai/gpt-oss-20b:free

GEMINI_API_KEY=your_api_key
```

## Google OAuth local setup

1. In Google Cloud Console, create or select a project and configure its OAuth consent screen.
2. Create an OAuth client with application type **Web application**.
3. Add this exact authorized redirect URI:

   ```text
   http://localhost:8000/auth/google/callback
   ```

4. Put the generated client ID and client secret in `backend/.env`. Never put either value in frontend files or commit them.
5. Keep the local URLs consistent:

   ```env
   FRONTEND_URL=http://localhost:5500
   GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
   DEBUG=true
   ```

6. If the Google consent screen is in **Testing** mode, add the Google account used for testing under **Test users**.
7. From `backend/`, verify the non-secret configuration:

   ```bash
   python scripts/verify_google_oauth.py
   ```

8. Start both servers using the commands above, open `http://localhost:5500`, and choose **Continue with Google**.

The expected browser flow is:

```text
frontend → /auth/google/start → Google
→ /auth/google/callback → frontend?auth=google
→ /auth/me → authenticated application
```

OAuth tokens remain on the backend. WUTT stores only a revocable, HTTP-only session cookie in the browser. Email/password login remains available.

If credentials are missing, the Google button returns to the login dialog with a configuration message. If Google reports `redirect_uri_mismatch`, compare the URI in Google Cloud with `GOOGLE_REDIRECT_URI` character-for-character, including scheme, port, path, and trailing slash.

## Temporary Chapter 6 demo login

Demo login is disabled by default. To enable one dedicated demo account, add
the following to `backend/.env` and restart the backend:

```env
DEMO_LOGIN_ENABLED=true
DEMO_LOGIN_EMAIL=demo@example.com
DEMO_LOGIN_PASSWORD=use-a-unique-demo-password
```

Use those exact credentials in the existing email login form. On the first
successful demo login, WUTT creates that one account with a bcrypt password
hash and issues the normal authentication cookie. Other invented credentials
remain invalid, and the configured demo email cannot be claimed through
registration.

Set `DEMO_LOGIN_ENABLED=false` while keeping `DEMO_LOGIN_EMAIL` configured to
block new logins for the persisted demo account. Existing sessions should be
logged out or allowed to expire. Google OAuth and regular email/password
authentication are unaffected. Never reuse a personal password or commit the
configured demo password.

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
