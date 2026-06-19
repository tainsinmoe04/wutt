# ch-3 Personal Project — Report

github_username: tainsinmoe04
personal_repo_url: https://github.com/tainsinmoe04/wutt
project_summary: WUTT is a wardrobe-based outfit recommendation MVP that lets a user register, add wardrobe items, set profile details, choose an occasion, and receive an outfit recommendation.
slides_url: slides/wutt-presentation.md

## Methodology

I built WUTT as a small vertical slice instead of trying to finish a large platform. I worked feature by feature: authentication, profile, wardrobe upload, recommendation logic, UI polish, and deployment. I used Claude Code throughout the process with project-level MCP, a reusable skill, and a debugging agent, and I made small commits as the project improved. The original idea included AI vision-based styling, but because the available proxy/model setup was not reliable for production image understanding, I scoped the MVP down to a working metadata-based recommendation flow with fallback logic.

## Evidence — Claude Code usage

### MCP
- path: .mcp.json
- what: Project-level MCP configuration used by Claude Code.

### Skill
- path: .claude/skills/wutt-autonomous/SKILL.md
- what: A reusable Claude Code skill for continuing WUTT work.

### Agent
- path: .claude/agents/wutt-debugger.md
- what: A WUTT-specific debugging agent for frontend, backend, auth, CORS, and deployment issues.
