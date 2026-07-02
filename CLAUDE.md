# CLAUDE.md — WUTT

## What WUTT Is

WUTT is an AI Fashion Companion for fashion-interested users.

Core message: "Know Your Wardrobe. Upgrade Your Style."

It is a consumer fashion product — not a dashboard, not a SaaS app, not an admin tool. Fashion first, AI second. Visual quality matters as much as functionality.

## Product Principles

- Visual before text
- Inspiration before configuration
- Personal before social
- Wardrobe before shopping
- Companion, not dashboard
- Fast inspiration — never make the user wait to see something
- Never feel empty — every screen should have life, even with no data
- AI should feel invisible — the user gets advice, not a tech demo

## Stack

Frontend: HTML + CSS + JavaScript
Backend: Python FastAPI + SQLAlchemy + SQLite
Deploy: Render.com
Font: Space Grotesk via Google Fonts

The current stack is not sacred. If a design skill recommends React, Tailwind, or a component rebuild for better product quality, explain the tradeoffs and ask before changing.

## Current Priority

Repo cleanup → skill/agent alignment → frontend polish → README → screenshots → slides.

Do not add new features unless explicitly approved.

## Design System

Primary:    #88A2FF    Deep:     #253A82
Energy:     #E3FC87    Blush:    #FFB2F7
Sky:        #C0E0FF    Lavender: #AB9DFF

Font: Space Grotesk. All colours via CSS variables. Use consistent naming and reusable classes.

## Conventions

Python: 4-space indent, type hints, docstrings
JS: 2-space indent, async/await, no jQuery
CSS: CSS custom properties for shared values
API responses: `{"status": "success/error", "data": {}, "message": ""}`

## Safety

- Never commit .env
- Never expose API keys in frontend JS
- Never push to main without permission
- Ask before deleting or restructuring files
- Do not claim backend services are working without testing
- Do not blindly add dependencies

## Output Style

Explain before editing. Show a plan before large changes. Be direct. No filler.
