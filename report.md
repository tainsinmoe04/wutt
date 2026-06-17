# WUTT — Assignment Ch-3 Report

## Project Information

- **Project**: WUTT AI Personal Stylist
- **Tagline**: "ဒီနေ့ ဘာဝတ်ရမလဲ?" — Myanmar's first AI outfit advisor
- **GitHub**: [https://github.com/tainsinmoe04/wutt](https://github.com/tainsinmoe04/wutt)
- **Live URL**: [https://wutt.onrender.com](https://wutt.onrender.com)
- **Student**: Tain Sin Moe
- **Date**: June 2026

---

## MCP Evidence

**File**: `.mcp.json`

Four MCP servers configured for the WUTT project:

| Server | Purpose |
|--------|---------|
| `superpowers` | Extended tooling capabilities for Claude Code |
| `taskmaster` | Task management — task creation, dependency tracking, status updates |
| `filesystem` | Secure file system operations within allowed directories |
| `fetch` | Web content fetching for API documentation lookups |

All servers were used throughout development — Task Master tracked progress across Tasks 9-17, filesystem handled project file operations, and fetch assisted with external documentation references.

---

## Skill Evidence

### 1. `.claude/skills/styling.md`
**Purpose**: On-demand context for AI outfit recommendation logic. Invoked when Claude needs to know WUTT's stylist-specific patterns — occasion mapping, Myanmar cultural context, color theory, OpenAI Vision prompt structure, and the standard recommendation response format.

### 2. `.claude/skills/backend.md`
**Purpose**: On-demand context for FastAPI backend patterns specific to WUTT. Covers the standard API response envelope (`status`/`data`/`message`), SQLAlchemy 2.0 ORM patterns, JWT auth flow, Cloudinary signed upload pattern, OpenAI Vision service integration, and anti-patterns to avoid (e.g., passlib incompatible with bcrypt 5.0.0, `check_same_thread=False` for SQLite).

Both skills follow the principle of **context-on-demand** — Claude only loads them when the task matches, keeping context lean.

---

## Agent Evidence

### `.claude/agents/outfit-reviewer.md`
**Type**: Read-only review subagent
**Purpose**: Reviews AI outfit recommendations for Myanmar cultural appropriateness, color harmony, weather practicality, occasion fit, and wearability. Invoked after every stylist recommendation — never modifies code, only reports findings.

**Key review dimensions**:
- Myanmar cultural sensitivity (pagoda, wedding, Thingyan, office)
- Longyi/htamein appropriateness
- Color-to-skin-tone matching
- Climate practicality (breathable fabrics in tropical heat)

---

## Methodology

**Approach**: Spec-first development using CLAUDE.md as the single source of truth.

### Development Workflow

1. **CLAUDE.md as Specification** — The project file at the root defines the entire spec: tech stack, file structure, database schema, API endpoints, design system, coding standards, security rules, and known anti-patterns. Every implementation decision was verified against CLAUDE.md.

2. **Skills for On-Demand Context** — `.claude/skills/styling.md` and `.claude/skills/backend.md` provide deep domain context only when needed. This keeps the main conversation context lean while ensuring specialized knowledge is available on demand.

3. **Hooks for Safety** — `.claude/hooks/safety-check.sh` blocks dangerous commands (force pushes, destructive git operations, npm install with unsafe flags, deletion of critical config files). Acts as a safety net for the development environment.

4. **Subagents for Unbiased Review** — Dedicated agents (`code-reviewer`, `outfit-reviewer`) perform adversarial review. Their system prompts encode WUTT-specific rules and anti-patterns from CLAUDE.md, ensuring every piece of code is checked against the project's own standards by a fresh, unbiased context.

5. **Incremental Delivery** — Each feature (auth → profile → wardrobe → stylist → dashboard) was built, tested independently via curl, reviewed by the code-reviewer agent, fixed, and committed before moving to the next. This prevented compounding errors and ensured every commit was deployable.

### Why This Approach

- **Deterministic quality**: CLAUDE.md eliminates ambiguity — every decision is verifiable against a written spec
- **Context efficiency**: Skills load on demand; agents carry their own context; main conversation stays focused
- **Catch errors early**: Subagent review before commit catches issues that the main context (biased by having written the code) would miss
- **Security by default**: CLAUDE.md's "NEVER do X" rules combined with hook-enforced safety prevents the most common foot-guns

---

## Project Statistics

| Metric | Value |
|--------|-------|
| Total source files | 20 |
| Total lines of code | 4,516 |
| API endpoints | 11 |
| Database tables | 4 |
| Git commits | 13 |
| MCP servers configured | 4 |
| Claude Code agents | 3 |
| Claude Code skills | 2 |
