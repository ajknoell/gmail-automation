# AI Agent System

Veloro includes an autonomous AI agent system that uses **Claude's tool_use** capability and **Firecrawl** web scraping to perform deep research, discover leads, and gather competitive intelligence.

## Overview

Three agents are available:

| Agent | Purpose | Input | Output |
|-------|---------|-------|--------|
| **Prospect Research** | Deep-research a lead's website and build a rich company profile | Lead with a website URL | Structured profile saved to lead's enrichment data |
| **Lead Discovery** | Find new businesses by crawling directories and listings | Industry + location | New Lead records (auto-enriched by EnrichmentWorker) |
| **Competitive Intelligence** | Research a competitor's website for pricing, features, positioning | Competitor URL | Intelligence report saved as a Signal |

## Architecture

```
API Request
    |
    v
[Route creates AgentTask record (status: pending)]
    |
    v
[Daemon thread spawned]
    |
    v
[AgentRunner: Claude tool_use loop]
    |--- calls firecrawl_map (discover site pages)
    |--- calls firecrawl_scrape (read page content)
    |--- calls web_search (search for news via Tavily)
    |--- calls save_* tool (capture structured output)
    |
    v
[Results saved to Lead/Signal + AgentTask updated (status: completed)]
```

### Key Components

| Component | File | Description |
|-----------|------|-------------|
| `FirecrawlService` | `backend/app/services/firecrawl_service.py` | REST API wrapper for Firecrawl (scrape, crawl, map) |
| `AgentRunner` | `backend/app/services/agent_framework.py` | Claude tool_use agentic loop with cancellation and token tracking |
| `AgentTool` | `backend/app/services/agent_framework.py` | Tool definition (name, schema, executor function) |
| `AgentTask` | `backend/app/models/agent_task.py` | SQLAlchemy model tracking task execution, results, and costs |

### Safety & Limits

- **15-iteration cap** — agents stop after 15 tool_use rounds to prevent runaway execution
- **Cancellation** — `threading.Event` checked between iterations; cancel via API
- **Rate limiting** — `FirecrawlService` enforces minimum 1-second intervals between API calls
- **Output truncation** — tool outputs capped at 15,000 characters to stay within context limits

---

## Agents

### Prospect Research

Autonomously maps and scrapes a lead's website to build a comprehensive company profile for personalized outreach.

**Process:**
1. Maps site structure with `firecrawl_map` to discover pages
2. Scrapes up to 5 key pages (about, team, services, blog)
3. Optionally searches for recent news via Tavily
4. Synthesizes a structured profile with `save_research_profile`

**Tools:** `firecrawl_map`, `firecrawl_scrape`, `web_search`, `save_research_profile`

**Output fields:** company overview, industry, key people (name + title), products/services, target market, company values, recent news, tech stack, talking points for outreach, year founded

**Data flow:** Results saved to `Lead.enrichment_data['agent_research']`. Concrete fields (`employee_count`, `decision_maker`, `year_founded`) also updated on the Lead record if discovered.

### Lead Discovery

Finds new business prospects by searching directories and listing sites for a given industry and location.

**Process:**
1. Searches web for directories, trade associations, and business listings
2. Scrapes directory pages with Firecrawl to extract listings
3. Gathers business name, website, phone, address, and description
4. Saves results via `save_discovered_leads`

**Tools:** `web_search`, `firecrawl_scrape`, `firecrawl_map`, `save_discovered_leads`

**Requirements:** Tavily API key (for web search)

**Data flow:** Creates new `Lead` records with `source='agent_discovery'` and `status='new'`. These are automatically picked up by the existing `EnrichmentWorker` for enrichment.

### Competitive Intelligence

Researches a competitor's website and produces an intelligence report covering products, pricing, positioning, and recent activity.

**Process:**
1. Maps competitor site structure
2. Scrapes key pages (pricing, features, about, blog)
3. Searches for recent competitor news
4. Synthesizes report via `save_intelligence_report`

**Tools:** `firecrawl_map`, `firecrawl_scrape`, `web_search`, `save_intelligence_report`

**Output fields:** competitor name, overview, products/services, pricing model and details, target market, positioning, strengths, weaknesses, recent changes, tech stack, key takeaways

**Data flow:** Report saved as a `Signal` record with `source_type='competitive_intel'` and `signal_type='competitor_report'`. Appears on the Signals page.

---

## API Reference

All endpoints require the `X-Workspace-Id` header.

### List Tasks

```
GET /api/agents/tasks?agent_type=prospect_research&status=completed&page=1&per_page=20
```

**Response:**
```json
{
  "tasks": [{ "id": 1, "agent_type": "prospect_research", "status": "completed", ... }],
  "total": 15,
  "page": 1,
  "pages": 1
}
```

### Get Task Detail

```
GET /api/agents/tasks/1
```

Returns full task including `config`, `result`, `execution_log`, and cost metrics.

### Start Prospect Research

```bash
curl -X POST http://localhost:5001/api/agents/research \
  -H 'Content-Type: application/json' \
  -H 'X-Workspace-Id: 1' \
  -d '{"lead_id": 42}'
```

**Response:** `202 Accepted` with the created `AgentTask` object.

**Requirements:** Lead must have a `website` field set.

### Start Lead Discovery

```bash
curl -X POST http://localhost:5001/api/agents/discover \
  -H 'Content-Type: application/json' \
  -H 'X-Workspace-Id: 1' \
  -d '{"industry": "HVAC", "location": "San Diego, CA", "criteria": "5-50 employees"}'
```

**Required:** `industry`. **Optional:** `location`, `criteria`.

### Start Competitive Intelligence

```bash
curl -X POST http://localhost:5001/api/agents/competitive-intel \
  -H 'Content-Type: application/json' \
  -H 'X-Workspace-Id: 1' \
  -d '{"competitor_url": "competitor.com", "competitor_name": "Acme Corp"}'
```

**Required:** `competitor_url`. **Optional:** `competitor_name`.

### Cancel Task

```bash
curl -X POST http://localhost:5001/api/agents/tasks/1/cancel \
  -H 'X-Workspace-Id: 1'
```

Only works on tasks with status `pending` or `running`.

### Usage Stats

```
GET /api/agents/stats
```

**Response:**
```json
{
  "total": 25,
  "completed": 20,
  "running": 1,
  "failed": 4,
  "total_input_tokens": 150000,
  "total_output_tokens": 45000,
  "total_firecrawl_pages": 87,
  "by_type": {"prospect_research": 15, "lead_discovery": 7, "competitive_intel": 3}
}
```

---

## Setup

### 1. Firecrawl API Key

Get a key at [firecrawl.dev](https://firecrawl.dev). Configure via either method:

- **Environment variable:** `export FIRECRAWL_API_KEY=fc-...`
- **Settings UI:** Navigate to `/settings` and enter the key in the "Firecrawl API Key" field

### 2. Anthropic API Key (required)

Already configured if you're using email personalization. The agent framework uses the same key.

### 3. Tavily API Key (optional)

Enables the `web_search` tool in agents for finding recent news and directories. Get a key at [tavily.com](https://tavily.com). Without it, agents still work but skip web search steps.

### 4. No New Dependencies

The agent system uses `requests` (already installed) for Firecrawl API calls and `anthropic` (already installed) for Claude. No new Python packages needed.

---

## Cost Tracking

Each `AgentTask` record tracks:
- `input_tokens` — Claude API input tokens consumed
- `output_tokens` — Claude API output tokens consumed
- `firecrawl_pages_scraped` — number of Firecrawl scrape calls made

Aggregate stats are available via `GET /api/agents/stats` and displayed on the frontend Agents page dashboard.

---

## Frontend

- **Agents page** (`/agents`) — Task list with filters, expandable details, research profile viewer, and usage stats dashboard
- **Pipeline page** — "Research" button on each lead row (appears when lead has a website)
- **Settings page** — Firecrawl API key input field

---

## File Reference

| File | Purpose |
|------|---------|
| `backend/app/services/firecrawl_service.py` | Firecrawl REST API wrapper (scrape, crawl, map) |
| `backend/app/services/agent_framework.py` | Claude tool_use agentic loop (AgentTool, AgentRunner, AgentResult) |
| `backend/app/models/agent_task.py` | AgentTask SQLAlchemy model |
| `backend/app/services/agents/__init__.py` | Agents package |
| `backend/app/services/agents/prospect_research.py` | Prospect research agent implementation |
| `backend/app/services/agents/lead_discovery.py` | Lead discovery agent implementation |
| `backend/app/services/agents/competitive_intel.py` | Competitive intelligence agent implementation |
| `backend/app/routes/agents.py` | API endpoints (7 routes) |
| `frontend/src/pages/Agents.jsx` | Agent management UI page |
| `frontend/src/api/client.js` | Agent API client functions |
