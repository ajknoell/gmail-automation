# Cowork + Claude Code: M&A Deal Sourcing Implementation Plan

**Date:** 2024-03-04
**Architecture Principle:** Cowork thinks, Claude Code acts. Data flows one direction: Claude Code outputs feed into Cowork for review and action.

---

## Division of Responsibility

| Layer | Owner | What It Does |
|-------|-------|-------------|
| **Thesis Generation** | Cowork | Generates acquisition thesis by vertical. Produces opportunity, why-now, pros, cons, recommendation. Read-only day-to-day; quarterly human-initiated updates. Daily job: audit deal flow against thesis. |
| **List Building** | Claude Code (Veloro) | Builds and maintains ranked target lists from scraped sources. Enriches with employee count, years in operation, location count, review volume. Feeds into Cowork and outreach pipeline. |
| **Outreach** | Claude Code infra, Cowork strategy | Volume and sequencing handled by Claude Code. Personalization strategy set once in Cowork at archetype level. Individual personalization is light: business name, geography, one operational detail. |

---

## Current Platform Capabilities (What Already Works)

### Scraping & Discovery
- **Google Maps/Places API** — Search by lat/lng, radius, type, keyword. Returns name, address, phone, website, rating, review count, business type, coordinates. (`places_service.py`, `map_explorer.py`)
- **Yelp Fusion API** — Parallel search with deduplication against Google results. Adds Yelp rating, review count, price range. (`yelp_service.py`, `business_search.py`)
- **Playwright Google Maps scraper** — Headless browser extraction of 20-50 businesses per search query. (`prospect_discovery.py`)
- **Firecrawl** — Single-page scrape, site map discovery, full-site crawl. Returns markdown + metadata. (`firecrawl_service.py`)

### Enrichment
- **Website scraping** — Scrapes 7 pages per domain (home, about, contact, team, etc.). Extracts emails, phones, employee count, year founded, decision maker name. (`enrichment_service.py`)
- **LinkedIn discovery** — Google search for LinkedIn company URL + employee count from snippets.
- **Retirement likelihood scoring** (0-100) — Tenure language, copyright year staleness, biographical signals, family business patterns, industry weighting, web search signals.
- **Lead scoring** (0-100) — Composite of website presence, contact info, employee count sweet spot, ratings, LinkedIn, decision maker, retirement likelihood.
- **Apollo.io** — Person search by title, location, domain, keywords. Returns email, phone, LinkedIn, company data.

### Outreach
- **Multi-step email sequences** — Configurable delays, follow-up logic, reply detection, auto-pause on reply.
- **AI personalization** — Claude generates per-recipient copy using business context, website analysis, custom fields.
- **Pre-written copy acceptance** — `personalized_subject` + `personalized_body` fields on Recipient. Upload via CSV or set via API. Bypasses AI generation entirely.
- **Confidence scoring** — 5-dimension evaluation (personalization, spam safety, coherence, relevance, historical match). Auto-send above threshold, review queue below.
- **Reply autopilot** — Sentiment classification, auto-response for positive replies.

### Deal Tracking
- **Full acquisition pipeline** — Stages: interested → contacted_broker → nda_signed → reviewing_financials → loi_submitted → under_contract → due_diligence → closed_won/lost.
- **Financial fields** — asking_price, revenue, cash_flow, SDE, EBITDA, offer_price.
- **Deal criteria** — Workspace-level filters for price, revenue, cash_flow, SDE, EBITDA, location, category, keywords.
- **Create from listing** — Auto-populates deal from scraped business listing data.

### Intelligence
- **Signal engine** — SSL expiry, job postings, news, website changes. Relevance scoring against business profile.
- **Daily brief** — Aggregates new prospects, replies, auto-responses, follow-ups due, pipeline stats, email stats.

---

## Workstream 1: Enhanced List Building

### Goal
Expand scraping sources beyond Google Maps/Yelp. Add state licensing databases, industry associations, and structured enrichment for the filters that matter: employee count, years in operation, location count, review volume.

### 1A. State Licensing Database Scrapers (NEW)

**Priority:** High — this is the highest-signal source for trades/services businesses (plumbing, HVAC, electrical, roofing, etc.)

**Implementation:**

Create `backend/app/services/scrapers/` module with a base scraper class and per-state implementations.

```
backend/app/services/scrapers/
├── __init__.py
├── base_scraper.py          # Abstract base: search(), parse(), normalize()
├── state_license_scraper.py # Orchestrator: routes to correct state scraper
├── states/
│   ├── __init__.py
│   ├── california.py        # CSLB (contractors), DCA (general)
│   ├── texas.py             # TDLR
│   ├── florida.py           # DBPR
│   └── ...                  # Add states incrementally
└── industry_directories.py  # HomeAdvisor, Angi, Thumbtack scraping
```

**Base scraper interface:**
```python
class BaseLicenseScraper:
    def search(self, license_type: str, location: str, **kwargs) -> list[dict]
    def parse_result(self, raw: dict) -> NormalizedBusiness
    def get_supported_license_types(self) -> list[str]
```

**Normalized output (shared across all scrapers):**
```python
@dataclass
class NormalizedBusiness:
    name: str
    owner_name: str | None
    address: str | None
    phone: str | None
    website: str | None
    license_number: str | None
    license_type: str | None
    license_status: str | None  # active, expired, suspended
    license_issue_date: date | None  # proxy for years in operation
    employee_count: int | None
    source: str  # 'cslb_ca', 'tdlr_tx', etc.
    source_url: str | None
    raw_data: dict  # preserve original for debugging
```

**New model: `DiscoverySource`**
```python
class DiscoverySource(db.Model):
    id: int
    workspace_id: int
    source_type: str  # 'state_license', 'google_maps', 'yelp', 'industry_dir'
    config: JSON       # {state, license_type, geography, etc.}
    last_run_at: datetime
    results_count: int
    schedule: str      # 'weekly', 'daily', 'manual'
    is_active: bool
```

**New route: `/api/discovery/sources`**
- `GET /` — List configured discovery sources
- `POST /` — Create new source (e.g., "California HVAC contractors in Los Angeles")
- `POST /:id/run` — Trigger a scan
- `GET /:id/results` — Get results with pagination

**Approach:** Use Firecrawl for state licensing sites that don't have APIs. Most state boards (CSLB, TDLR, DBPR) have searchable web interfaces — scrape the search results page. For states with open data portals (some publish CSV/JSON), use direct downloads.

**Phase 1 targets (highest ROI):**
- California (CSLB) — largest contractor market
- Texas (TDLR) — fast-growing market
- Florida (DBPR) — high retirement demographics

### 1B. Enrichment Layer Enhancement

**Current gaps vs. what's needed:**

| Field | Current State | Needed Enhancement |
|-------|--------------|-------------------|
| Employee count | ✅ Website + LinkedIn snippets | Add Google Maps "busy times" as signal; cross-reference Yelp employee_count field |
| Years in operation | ⚠️ `year_founded` extracted from websites | Add license issue date as primary source; BBB accreditation date as backup |
| Location count | ❌ Not tracked | Add multi-location detection: Google Maps search by business name across geo, count unique addresses |
| Review volume | ✅ Google review count + Yelp review count | Aggregate into `total_review_volume` field; add review velocity (reviews/year) |

**Changes to Lead model:**
```python
# Add to Lead model
location_count = db.Column(db.Integer)           # Number of locations detected
total_review_volume = db.Column(db.Integer)       # Google + Yelp reviews combined
review_velocity = db.Column(db.Float)             # Reviews per year (growth proxy)
years_in_operation = db.Column(db.Integer)         # Computed from license date or year_founded
license_number = db.Column(db.String(100))
license_status = db.Column(db.String(50))
license_issue_date = db.Column(db.Date)
owner_name = db.Column(db.String(200))             # From license records
data_sources = db.Column(db.Text)                  # JSON: ["google", "yelp", "cslb_ca"]
```

**Enhance `enrichment_service.py`:**
- After website enrichment, check if `year_founded` is missing → fall back to `license_issue_date`
- Compute `years_in_operation = current_year - max(year_founded, license_issue_date.year)`
- Add `_detect_location_count()` method: search Google Places for exact business name in wider radius, count distinct addresses
- Add `_compute_review_volume()`: sum Google + Yelp review counts, compute velocity if year_founded known

### 1C. Thesis-Aware Lead Scoring

**Current lead scoring** is a generic composite (website, phone, email, employee count, rating, reviews, LinkedIn, decision maker, retirement). This needs a thesis-aware layer.

**New model: `AcquisitionThesis`**
```python
class AcquisitionThesis(db.Model):
    id: int
    workspace_id: int
    name: str                    # "HVAC Roll-up in Sun Belt"
    vertical: str                # "HVAC", "Plumbing", "Electrical"
    status: str                  # 'active', 'paused', 'archived'

    # Criteria (all optional — filters applied as AND)
    min_employee_count: int
    max_employee_count: int
    min_years_in_operation: int
    max_years_in_operation: int
    min_location_count: int
    max_location_count: int
    min_review_volume: int       # Revenue proxy
    target_geographies: JSON     # ["California", "Texas", "Florida"]
    target_categories: JSON      # ["HVAC", "plumbing"]
    exclude_categories: JSON

    # Thesis document (Cowork-generated, human-approved)
    thesis_document: Text        # Markdown: opportunity, why-now, pros, cons, recommendation
    thesis_updated_at: datetime

    created_at: datetime
    updated_at: datetime
```

**New service: `thesis_scorer.py`**
```python
class ThesisScorer:
    def score_lead(self, lead: Lead, thesis: AcquisitionThesis) -> ThesisScore:
        """Score a lead against a specific acquisition thesis. Returns 0-100."""

    def score_batch(self, leads: list[Lead], thesis: AcquisitionThesis) -> list[ThesisScore]:
        """Score a batch of leads efficiently."""

    def rank_leads(self, workspace_id: int, thesis_id: int, limit: int = 50) -> list[dict]:
        """Return top leads ranked by thesis fit score."""
```

**Scoring factors:**
- Employee count within thesis range: 25 points
- Geography match: 20 points
- Category match: 20 points
- Years in operation within range: 15 points
- Review volume (revenue proxy): 10 points
- Location count within range: 10 points

**New routes: `/api/thesis/`**
- `GET /` — List theses for workspace
- `POST /` — Create thesis (Cowork pushes thesis document here)
- `PUT /:id` — Update thesis (quarterly refresh)
- `GET /:id/targets` — Ranked lead list against this thesis
- `GET /:id/report` — Weekly structured deal flow report

---

## Workstream 2: Weekly Structured Deal Flow Report

### Goal
Produce a structured weekly report that Cowork consumes to audit deal flow against thesis.

**New route: `GET /api/reports/weekly-deal-flow`**

**Response format (designed for Cowork consumption):**
```json
{
  "report_period": {
    "start": "2024-02-26",
    "end": "2024-03-04"
  },
  "thesis_summaries": [
    {
      "thesis_id": 1,
      "thesis_name": "HVAC Roll-up in Sun Belt",
      "new_targets_discovered": 23,
      "targets_enriched": 18,
      "targets_meeting_criteria": 12,
      "top_targets": [
        {
          "lead_id": 456,
          "name": "Smith's HVAC Inc",
          "location": "Phoenix, AZ",
          "employee_count": 35,
          "years_in_operation": 22,
          "review_volume": 847,
          "retirement_score": 78,
          "thesis_fit_score": 92,
          "enrichment_summary": "Owner John Smith, est. 2002, 3 locations, high retirement likelihood",
          "status": "discovered"  // or "enriched", "contacted", "replied"
        }
      ],
      "outreach_stats": {
        "emails_sent": 45,
        "opens": 18,
        "replies": 3,
        "positive_replies": 2
      },
      "pipeline_movement": {
        "new_interested": 2,
        "moved_to_contact": 1,
        "stage_changes": [
          {"deal": "ABC Corp", "from": "interested", "to": "contacted_broker"}
        ]
      }
    }
  ],
  "cross_thesis_stats": {
    "total_targets_discovered": 67,
    "total_emails_sent": 134,
    "total_replies": 8,
    "active_deals": 5,
    "pipeline_value": 2450000
  }
}
```

**Implementation:**
- New service `backend/app/services/report_service.py`
- Queries across Lead, Deal, EmailLog, ReplyMessage, AcquisitionThesis tables
- Aggregates by thesis and time period
- Can be triggered on schedule or on-demand

---

## Workstream 3: Outreach Integration with Cowork

### Goal
Cowork sets personalization strategy at the archetype level. Claude Code accepts that strategy and executes sends. Individual personalization is light: business name, geography, one operational detail.

### 3A. Archetype-Based Personalization

**New model: `OutreachArchetype`**
```python
class OutreachArchetype(db.Model):
    id: int
    workspace_id: int
    thesis_id: int | None        # Optional link to thesis
    name: str                    # "Owner-Operator Trades/Services"
    description: str

    # Personalization strategy (Cowork-authored)
    tone: str                    # "peer-to-peer", "professional", "casual"
    trigger_themes: JSON         # ["years of ownership", "succession", "lifestyle change"]
    avoid_themes: JSON           # ["product features", "technical specs", "ROI metrics"]
    value_proposition: str       # Core message in Cowork's words
    subject_line_formula: str    # Template pattern: "{{business_name}} — quick question about {{trigger}}"
    opening_formula: str         # "I noticed {{operational_detail}} about {{business_name}}..."
    cta_style: str               # "soft-ask", "direct-meeting", "info-share"

    # Personalization fields to include (light touch)
    required_fields: JSON        # ["business_name", "geography", "operational_detail"]
    optional_fields: JSON        # ["years_in_business", "owner_name"]

    created_at: datetime
    updated_at: datetime
```

**How it connects to existing Campaign system:**

The existing `Campaign` model already supports:
- `ai_prompt` — Custom instructions for Claude AI personalization
- `campaign_context` — Things to include in every email
- `use_ai_personalization` — Toggle AI vs. pre-written

**Enhancement: Link campaigns to archetypes.**
```python
# Add to Campaign model
archetype_id = db.Column(db.Integer, db.ForeignKey('outreach_archetypes.id'))
```

When `archetype_id` is set, the AI personalization prompt is auto-generated from the archetype's strategy fields rather than requiring manual `ai_prompt` authoring. This is the bridge: Cowork writes the archetype once, every campaign using that archetype gets consistent personalization.

**New routes: `/api/archetypes/`**
- `GET /` — List archetypes
- `POST /` — Create archetype (Cowork pushes strategy here)
- `PUT /:id` — Update archetype
- `GET /:id/preview` — Generate sample emails using archetype strategy for review

### 3B. Cowork → Claude Code Campaign Trigger

**New route: `POST /api/campaigns/from-thesis`**

Cowork identifies targets from the weekly report, sets the archetype, and triggers a campaign:

```json
POST /api/campaigns/from-thesis
{
  "thesis_id": 1,
  "archetype_id": 3,
  "lead_ids": [456, 789, 1011],  // Or omit for "all thesis-fit leads"
  "sequence_template_id": 5,      // Pre-built sequence (initial + 2 follow-ups)
  "send_window": {
    "start_hour": 8,
    "end_hour": 17,
    "timezone": "America/Phoenix",
    "days": ["mon", "tue", "wed", "thu", "fri"]
  }
}
```

This endpoint:
1. Creates a Campaign linked to thesis + archetype
2. Converts qualifying leads to Recipients (using existing Lead → Contact → Recipient flow)
3. Populates `custom_fields` from lead enrichment data
4. Sets `ai_prompt` from archetype strategy
5. Returns campaign ID for monitoring

---

## Workstream 4: Cowork Data API (MCP-Ready Endpoints)

### Goal
Expose all platform data via clean, read-focused endpoints that Cowork can consume. These are the endpoints a Cowork MCP integration would call.

### 4A. Structured Data Export Endpoints

All endpoints return JSON designed for Cowork plugin consumption.

```
GET /api/cowork/targets
  ?thesis_id=1
  &min_score=70
  &status=discovered|enriched|contacted
  &limit=50
  → Ranked target list with full enrichment data

GET /api/cowork/deals
  ?stage=interested,contacted_broker
  → Active deals with financial data and stage history

GET /api/cowork/replies
  ?since=2024-02-26
  ?sentiment=positive,neutral
  → Recent replies with sentiment, contact context, thread history

GET /api/cowork/signals
  ?since=2024-02-26
  &min_relevance=60
  → High-relevance signals for deal evaluation

GET /api/cowork/report/weekly
  → Weekly deal flow report (Workstream 2)

GET /api/cowork/report/daily-brief
  → Enhanced daily brief with thesis context
```

### 4B. Webhook Events (Cowork Notification)

**New model: `WebhookSubscription`**
```python
class WebhookSubscription(db.Model):
    id: int
    workspace_id: int
    url: str                # Cowork webhook endpoint
    events: JSON            # ["reply.positive", "deal.stage_change", "target.high_score"]
    is_active: bool
    secret: str             # HMAC signing key
    created_at: datetime
```

**Events emitted:**
| Event | Trigger | Payload |
|-------|---------|---------|
| `reply.received` | Any reply detected | contact, sentiment, message preview |
| `reply.positive` | Positive sentiment reply | contact, full thread, deal if linked |
| `deal.stage_change` | Deal moves stages | deal, old_stage, new_stage |
| `target.discovered` | Lead scores above thesis threshold | lead, thesis, score |
| `target.enriched` | Enrichment completes on lead | lead, enrichment_data |
| `campaign.completed` | Sequence finishes for all recipients | campaign stats |
| `report.weekly` | Weekly report generated | report URL |

**Implementation:** Add webhook dispatch to existing service methods. Use background thread for HTTP POST to avoid blocking request handlers.

---

## Implementation Priority & Phasing

### Phase 1: Data Foundation (Weeks 1-3)
1. **Lead model enhancements** — Add location_count, total_review_volume, review_velocity, years_in_operation, license fields, owner_name, data_sources
2. **AcquisitionThesis model** — CRUD routes + basic scoring
3. **Enrichment enhancements** — Multi-location detection, review aggregation, years computation
4. **Weekly report endpoint** — Aggregation service + `/api/reports/weekly-deal-flow`

### Phase 2: List Building Expansion (Weeks 3-6)
5. **Scraper base framework** — `backend/app/services/scrapers/` module with base class
6. **California CSLB scraper** — First state license scraper
7. **Texas TDLR + Florida DBPR scrapers** — Expand coverage
8. **DiscoverySource model** — Configurable, schedulable scraping
9. **Thesis-aware scoring** — `thesis_scorer.py` with ranked lead endpoints

### Phase 3: Outreach Integration (Weeks 5-7)
10. **OutreachArchetype model** — CRUD routes
11. **Archetype → Campaign bridge** — Auto-generate AI prompts from archetype strategy
12. **`/api/campaigns/from-thesis` endpoint** — Thesis-driven campaign creation
13. **Archetype preview** — Generate sample emails for Cowork review

### Phase 4: Cowork API Layer (Weeks 7-9)
14. **`/api/cowork/*` endpoints** — Read-focused data export layer
15. **WebhookSubscription model** — Event notification system
16. **Webhook dispatch** — Background HTTP POST on key events
17. **MCP server wrapper** — Optional: wrap `/api/cowork/*` as MCP tools for direct Cowork plugin consumption

---

## File Impact Summary

### New Files
```
backend/app/models/acquisition_thesis.py
backend/app/models/outreach_archetype.py
backend/app/models/discovery_source.py
backend/app/models/webhook_subscription.py
backend/app/routes/thesis.py
backend/app/routes/archetypes.py
backend/app/routes/cowork.py
backend/app/routes/reports.py
backend/app/routes/webhooks.py
backend/app/services/thesis_scorer.py
backend/app/services/report_service.py
backend/app/services/webhook_dispatcher.py
backend/app/services/scrapers/__init__.py
backend/app/services/scrapers/base_scraper.py
backend/app/services/scrapers/state_license_scraper.py
backend/app/services/scrapers/states/__init__.py
backend/app/services/scrapers/states/california.py
backend/app/services/scrapers/states/texas.py
backend/app/services/scrapers/states/florida.py
backend/app/services/scrapers/industry_directories.py
```

### Modified Files
```
backend/app/models/lead.py          — New fields for enhanced enrichment
backend/app/models/campaign.py      — Add archetype_id FK
backend/app/__init__.py             — Register new blueprints + migrations
backend/app/services/enrichment_service.py — Multi-location, review aggregation, years computation
```

### Not Modified (Leverage As-Is)
```
backend/app/services/places_service.py    — Google Maps integration
backend/app/services/yelp_service.py      — Yelp integration
backend/app/services/firecrawl_service.py — Web scraping
backend/app/services/campaign_runner.py   — Email sending
backend/app/services/claude_service.py    — AI personalization
backend/app/models/deal.py               — Deal pipeline
backend/app/models/deal_criteria.py       — Deal filters
```

---

## Key Design Decisions

1. **Thesis is read-only in Claude Code.** Cowork generates and updates the thesis document. Claude Code stores it and scores against it. No autonomous thesis modification.

2. **Archetype replaces per-campaign prompt writing.** Instead of crafting `ai_prompt` for each campaign, set it once at the archetype level. Campaigns inherit.

3. **License scrapers use Firecrawl, not Playwright.** State licensing sites are simple HTML. Firecrawl is more reliable and already integrated. Fall back to Playwright only if JavaScript rendering is required.

4. **Webhook events are fire-and-forget.** Dispatch in background thread. Retry once on failure. Log failures for debugging. Don't block the request handler.

5. **`/api/cowork/*` is a read-only view layer.** It doesn't duplicate routes — it reshapes existing data for Cowork consumption with thesis context included. Mutations go through existing endpoints.

6. **Employee count is the primary size proxy.** Revenue is unavailable for private companies. Review volume is the secondary signal. Both are already captured.
