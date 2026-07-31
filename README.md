# Fieldwork MCP

**Ask your pest control business questions in plain English.**

Works with Claude, Cursor, Codex, and other AI apps that support [MCP](https://modelcontextprotocol.io/).

> “How many customers do I have?”  
> “Who owes me money?”  
> “How much Alpine did we use this week?”  
> “Who did the most jobs?”

Your AI asks Fieldwork. You get a clear answer.  
**Read-only** — it can’t change jobs, charge cards, or edit customers.

Site: [`landing/index.html`](landing/index.html) (Relay home) · [`landing/fieldwork.html`](landing/fieldwork.html) (Ask Fieldwork) · Roadmap: [`ROADMAP.md`](ROADMAP.md)

---

## Who this is for

Pest and lawn-care owners who run **[Fieldwork](https://fieldworkhq.com/)** and want answers without digging through reports.

---

## Why can’t they just ask Claude or Cursor to set it up?

**Often they can** — if they’re already in Cursor or Claude Code with this project open, say:

> Set up Fieldwork MCP for me. I’ll paste my API key into `.env`.

The agent can create the venv, write MCP config, and wire the launcher.

You still need to **get the API key yourself** (it’s your Fieldwork password-equivalent).  
Don’t paste the key into a random chat if you can drop it straight into `.env`.

**When a copy-paste snippet still helps**

- You’re on the **website** and don’t have an agent in the folder yet  
- You’re on **Claude Desktop**, which doesn’t edit your disk the same way  
- Someone else is setting up a machine without opening this repo  

The endgame (see Roadmap) is a **one-line remote URL + login**, like LandingFolio — no Terminal, no JSON.

---

## What you can ask

### Customers
- How many customers do I have?
- Do I have a customer named ___?

### Money
- Who owes me money?
- How much did we make this month?
- How is business doing?

### Product
- How much product was used?
- What chemicals do we carry?

### Schedule, routes & technicians
- What’s on the schedule this week?
- Who are my technicians?
- How are my routes doing?
- Who did the most jobs?

**Bonus prompt:** `monday_morning_briefing` — one bundled ops snapshot.

---

## Quick start

### 1. Get your Fieldwork API key

Easiest path (in the Fieldwork app):

1. Go to **[Settings → Users & Routes](https://app.fieldworkhq.com/settings/users)**
2. Open your user (or an API Integration user)
3. Open the **Integration** tab and copy the **API Key**

Help: [Fieldwork APIs](https://intercom.help/fieldwork/en/articles/2406552-fieldwork-apis)

### 2. Install

```bash
git clone https://github.com/daisydaines/fieldwork-mcp.git
cd fieldwork-mcp
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
cp .env.example .env
# put FIELDWORK_API_KEY=... in .env
```

### 3. Connect your AI app

**Cursor** — `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "fieldwork": {
      "command": "/ABS/PATH/TO/fieldwork-mcp/scripts/run_mcp.sh"
    }
  }
}
```

**Claude Desktop** — same JSON in  
`~/Library/Application Support/Claude/claude_desktop_config.json`

**Claude Code:**

```bash
claude mcp add fieldwork -- /ABS/PATH/TO/fieldwork-mcp/scripts/run_mcp.sh
```

**Codex** — add a stdio MCP server pointing at `scripts/run_mcp.sh` (same idea as Cursor).

Then restart the app and ask: *How many customers do I have?*

### Optional: hosted connect (no Dropbox-style OAuth)

Fieldwork does not offer a third-party OAuth login popup. Closest path:

```bash
./scripts/run_mcp_http.sh
# open http://127.0.0.1:8000/connect
```

Paste your API key once. You get a bearer token and a one-line snippet for Claude / Cursor / Codex.
MCP endpoint: `http://127.0.0.1:8000/mcp` with `Authorization: Bearer <token>`.

---

## Safety

| Can do | Cannot do |
| --- | --- |
| Read customers, jobs, invoices, usage | Create or edit customers |
| Summarize routes & techs | Cancel or reschedule jobs |
| Report product used on jobs | Take payments or change prices |

Tools are annotated `readOnlyHint`. The HTTP client **refuses non-GET** requests.

---

## For builders

```bash
pip install -e ".[dev]"
pytest
ruff check src tests
./scripts/run_mcp.sh          # stdio
./scripts/run_mcp_http.sh     # streamable-http
```

Auth to Fieldwork: `api-key` header (default).

Unofficial. Not affiliated with Fieldwork / Anstar Products.

## License

MIT — see [LICENSE](LICENSE).
