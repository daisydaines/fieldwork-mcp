# Roadmap — cutting-edge distribution

Today Fieldwork MCP is a **local stdio** server with owner-shaped tools.
That’s the right product brain. What’s left is making it as easy as
[LandingFolio MCP](https://www.landingfolio.com/mcp): one URL, no Terminal.

## Done / in progress

| Capability | Status |
| --- | --- |
| Owner-shaped tools + `answer` strings | Done |
| Read-only HTTP client | Done |
| Tool annotations (`readOnlyHint`, etc.) | Done |
| Prompt: `monday_morning_briefing` | Done |
| Local **streamable-http** transport | Done (`./scripts/run_mcp_http.sh`) |
| `/connect` vault (paste API key → bearer token) | Done |
| Remote hosted MCP URL (public HTTPS) | Next |
| True Fieldwork OAuth login popup | Blocked (Fieldwork has no third-party OAuth app) |
| Progressive tool loading | Later (when tool count gets huge) |

## Phase 1 — Remote HTTP MCP (local first)

Already supported for local testing:

```bash
./scripts/run_mcp_http.sh
# → http://127.0.0.1:8000/mcp
```

Clients that speak Streamable HTTP can connect to that URL.

**Next:** deploy the same process behind HTTPS (Fly.io / Railway / Render / Vercel+container)
with auth headers, e.g.:

```bash
claude mcp add --transport http fieldwork \
  https://mcp.yourdomain.com/mcp \
  --header "Authorization: Bearer <user-token>"
```

## Phase 2 — Connect flow (done locally; host next)

**Why not Dropbox/Fathom OAuth?** Those products ship a real OAuth consent app.
Claude/Cursor can open a browser login. Fieldwork only exposes API keys, so there is
no login window we can pop. Closest smooth path:

1. Owner opens `/connect` (local now; public HTTPS next)
2. Pastes Fieldwork API key once
3. We verify it, encrypt it in a vault, mint a bearer token
4. Owner pastes one snippet into Claude/Cursor/Codex

If Fieldwork ever adds third-party OAuth, swap step 2 for a real login popup.

## Phase 3 — Resources & progressive tools

- **Resources:** pinned snapshots (“this week’s AR”, “route board”) agents can read without a tool call
- **Progressive loading:** keep a small owner-tool set always loaded; expose deeper `search_*` tools on demand
- **Landing video walkthrough:** short owner-friendly setup video (later)

## Why owners still paste config today

See README “Why can’t Claude just set it up?” — short version:
Cursor/Claude Code *can* configure local files if the project is open; a public
landing page visitor has no agent in their folder yet. Hosted HTTP + token removes the paste.
