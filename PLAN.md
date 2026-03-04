# Triggers & Signals: Review + Full UX Redesign

## Part 1: Functionality Review — What Works, What Doesn't

### Triggers (Website Monitoring)

**What it does:** Monitors contact websites for SSL expiry, downtime, content changes, copyright year.

| Trigger Type | Useful? | Verdict |
|---|---|---|
| `ssl_expiry` | Yes, for web agencies | **Keep** — great opener for web services outreach |
| `downtime` | Yes, for web agencies | **Keep** — urgent pain point, high-intent signal |
| `content_change` | Marginal | **Keep but improve** — too generic now (just a hash change). Needs context on *what* changed |
| `copyright_outdated` | Yes, for web agencies | **Keep** — easy visual signal of neglect |
| `review_change` | Partially implemented | **Keep** — useful for reputation management outreach |

**Key issue:** These triggers are highly relevant for a web design/dev workspace but nearly irrelevant for a business acquisition workspace. The system correctly supports per-workspace configuration, but the UI doesn't help the user understand which triggers matter for THEIR use case.

### Signals (Intent Detection)

**What it does:** Searches the web for hiring activity and company news for each contact's company.

| Signal Source | Useful? | Verdict |
|---|---|---|
| `job_posting` | Contextual | **Keep** — indicates company growth. For biz acquisition: could indicate owner overwhelm |
| `news` | Very useful | **Keep** — funding, leadership changes, expansions. For biz acquisition: owner transitions, retirement mentions |

**Missing signal types that would be high-value (future work):**
- Business-for-sale listings (BizBuySell, etc.)
- Owner/founder LinkedIn activity suggesting transition
- Revenue stagnation signals
- Industry consolidation news
- Succession planning keywords

### Opportunities (Ranked Feed)

**What it does:** Aggregates all signals per contact, ranks by combined intent + relevance score.

**Verdict: This is the most useful view** — but it has NO sidebar navigation link and is only discoverable via a link in the Signals empty state. Almost certainly invisible to users.

### Cross-Feature Issues

1. **Confusing taxonomy:** Three separate pages (Triggers, Signals, Opportunities) for what is conceptually ONE thing: "reasons to reach out right now"
2. **Opportunities page has no nav link** — the best view is the hardest to find
3. **"Signals" nav section** contains both Triggers and Signals — confusing naming
4. **Section defaults to collapsed** — easy to miss entirely
5. **No onboarding** — user lands on empty pages with zero context
6. **`alert()` used instead of toast** — jarring UX on Triggers page
7. **Raw JSON displayed** — `JSON.stringify(t.current_value)` shown directly
8. **No explanation of business value** — user doesn't know WHY they should care
9. **Source setup is hidden** — behind a button click with no guidance
10. **Scores shown without context** — "72% intent" means nothing to a new user

---

## Part 2: Full UX Redesign

### Core Insight

Triggers, Signals, and Opportunities are three views of ONE concept: **"AI-powered intelligence that tells you when and why to reach out."** We unify them.

### Information Architecture Change

**Before (confusing):**
```
Sidebar > Signals (collapsed by default)
  ├── Listings
  ├── Triggers     → /triggers
  └── Signals      → /signals
  /opportunities   → (NO NAV LINK - hidden)
```

**After (clear):**
```
Sidebar > Intelligence (expanded, prominent)
  ├── Radar        → /intelligence         (unified feed + opportunities)
  ├── Triggers     → /intelligence/triggers (website monitoring detail)
  └── Sources      → /intelligence/sources  (configure what to monitor)

  Listings → moves to "Find" section
```

### The Three Views

#### View 1: Radar (Main Intelligence Page) — `/intelligence`

Replaces Signals page AND Opportunities page. Primary view.

**Empty State (first visit — the "wow" pitch):**
- Hero section with clear value proposition
- Three illustrated cards showing what AI monitors: Website Issues, News & Funding, Hiring Activity
- Step-by-step getting started guide: 1) Add contacts 2) Enable sources 3) AI does the rest
- Single CTA button: "Set Up Sources"

**Active State (has data):**
Two tabs: **Feed** | **Top Opportunities**

- **Feed tab:** Chronological timeline of all events (triggers + signals merged). Each card has icon, human-readable title, contact + company, plain-English summary (NOT raw JSON), relative timestamp, severity indicator, one-click "Create Outreach" button
- **Top Opportunities tab:** Contact-centric ranked view with combined score visualization and signal count per contact

#### View 2: Triggers Detail — `/intelligence/triggers`

Keeps dedicated trigger management but with improved UX:
- Better empty state explaining what website monitoring does
- Human-readable trigger details instead of raw JSON
- Toast notifications instead of `alert()`
- "Why this matters" context on each trigger type

#### View 3: Sources Configuration — `/intelligence/sources`

Currently buried behind a button. Gets its own page:
- Card-based source display with descriptions
- Toggle to enable/disable
- Status: "Checking 23 websites every 24h · Last check: 2h ago"

### Signal Card Redesign

**Before:**
```
🔒 SSL Expiring  [critical]
John Smith - ACME Corp
Detected: 3/4/2026
{"ssl_expiry_date": "2026-03-16", "days_remaining": 12}
                            [Create Outreach] [Dismiss]
```

**After:**
```
● critical
🔒  SSL Certificate Expiring Soon
John Smith · ACME Corp

Their SSL certificate expires in 12 days. Websites with
expired certificates show security warnings to visitors —
a natural reason to reach out.

2 hours ago · via Website Monitor
                [ ✨ Create Outreach ]  [ Dismiss ]
```

### Outreach Preview Enhancement

When AI generates an email:
1. Show the triggering signal at top: "Based on: SSL certificate expiring in 12 days"
2. Add "Copy to Clipboard" and "Regenerate" actions
3. Better visual formatting

---

## Part 3: Implementation Steps

### Step 1: Create unified Intelligence/Radar page
- New file: `frontend/src/pages/Intelligence.jsx`
- Combines Feed (triggers + signals merged) and Top Opportunities tabs
- Rich empty state with onboarding guidance
- Human-readable signal cards

### Step 2: Create Sources configuration page
- New file: `frontend/src/pages/IntelligenceSources.jsx`
- Card-based source display with enable/disable, status, descriptions

### Step 3: Update Triggers page
- Replace `alert()` with toast
- Format raw JSON into human-readable descriptions
- Better empty state with value explanation

### Step 4: Update navigation and routing
- Rename sidebar section from "Signals" to "Intelligence"
- Default to expanded
- Add nav items: Radar, Triggers, Sources
- Add route aliases so old URLs still work
- Move Listings to "Find" section

### Step 5: Enhanced outreach modal
- Show triggering signal context
- Add copy-to-clipboard
- Add "Regenerate" action

### Step 6: Backend — human-readable summaries
- Helper methods for plain-English trigger descriptions
- Format `current_value` into readable sentences
