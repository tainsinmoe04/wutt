---
name: wutt-autonomous
description: Autonomous continuation loop for WUTT — builds, debugs, reviews, commits, and pushes without user intervention.
---

# WUTT Autonomous Skill

Continue working on the WUTT project autonomously. Follow this loop until all tasks are done or blocked.

## Autonomous Loop Protocol

```
┌─────────────────────────────────────────────────┐
│  1. ASSESS  — Read tasks.json, git status       │
│  2. PLAN    — Decide what to work on next       │
│  3. BUILD   — Implement the change              │
│  4. REVIEW  — Spawn wutt-reviewer agent         │
│  5. FIX     — Address review findings           │
│  6. COMMIT  — Atomic commit with clear message  │
│  7. PUSH    — Push to main                      │
│  8. REPEAT  — Go to 1 until done or blocked     │
└─────────────────────────────────────────────────┘
```

## Agent Delegation

### When to use wutt-debugger
- Auth flow issues (login → dashboard → API call → 401)
- CORS configuration problems
- Data serialization errors
- Cross-origin cookie/token issues

### When to use wutt-reviewer
- Before every commit
- After significant multi-file changes
- When touching security-sensitive code

### When to use wutt-orchestrator
- Complex multi-layer tasks (frontend + backend + deploy)
- Tasks requiring coordination between 3+ agents

## Commit Rules
- One commit per logical change
- Message format: `type: description` (e.g., `fix:`, `feat:`, `chore:`)
- Always include `Co-Authored-By: Claude <noreply@anthropic.com>`
- Never commit .env files
- Never push `git push origin main` (use `git push` for upstream)

## Stop Conditions
- All tasks in tasks.json are `done`
- A blocker requires user input (ask clearly, don't guess)
- Git status is clean with no pending changes
- 3 consecutive review cycles find no issues

## WUTT-Specific Context
- Backend: Python FastAPI at `wutt.onrender.com`
- Frontend: Vanilla JS at `wutt-frontend.onrender.com`
- CORS allows: `localhost:3000`, `wutt-frontend.onrender.com`
- Auth: JWT in Authorization header (primary) + httpOnly cookie (fallback)
- Database: SQLite at `backend/wutt.db`
