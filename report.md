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
- path: .claude/skills/styling.md
- what: A reusable Claude Code skill documenting WUTT's fashion intelligence — occasion matching, item classification, outfit scoring, and recommendation rules.

### Agent
- path: .claude/agents/wutt-reviewer.md
- what: A code review agent with 6 dimensions — correctness, security, style, architecture, cross-origin safety, and anti-patterns.

### CLAUDE.md
- path: CLAUDE.md
- what: Project-level instructions defining WUTT's identity, product principles, design system, conventions, and safety rules.

### Slides
- path: slides/wutt-presentation.md
- what: Marp slide deck styled with the WUTT design system.

### README
- path: README.md
- what: Project documentation with setup instructions, tech stack, and design system.
