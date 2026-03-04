# Veloro

**AI-powered outreach automation platform for finding prospects, personalizing email campaigns, and managing the full sales pipeline.**

Veloro combines prospect discovery, AI email personalization (via Claude), multi-step campaign orchestration, engagement tracking, and CRM-style contact management into a single self-hosted application. It is designed for B2B outreach teams, agencies, and solo operators who want full control over their data and workflows without per-seat SaaS fees.

---

## Table of Contents

- [Core Capabilities](#core-capabilities)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Feature Inventory](#feature-inventory)
  - [Command Center](#command-center)
  - [Prospect Discovery](#prospect-discovery)
  - [Contact Management](#contact-management)
  - [Email Campaigns](#email-campaigns)
  - [Quick Send](#quick-send)
  - [Reply Hub](#reply-hub)
  - [Templates](#templates)
  - [Pipeline Management](#pipeline-management)
  - [Insights & Analytics](#insights--analytics)
  - [Listings Monitor](#listings-monitor)
  - [Triggers](#triggers)
  - [Signals](#signals)
  - [Opportunity Feed](#opportunity-feed)
  - [Business Profile](#business-profile)
  - [Workspaces](#workspaces)
  - [Settings & Configuration](#settings--configuration)
- [Project Structure](#project-structure)
- [Data Models](#data-models)
- [Backend Services](#backend-services)
- [API Surface](#api-surface)
- [Setup & Configuration](#setup--configuration)
- [Strategic Positioning](#strategic-positioning)
- [Roadmap](#roadmap)

---

## Core Capabilities

| Capability | Description |
|---|---|
| **Find** | Discover prospects via Google Maps, Yelp, automated web discovery, and manual import |
| **Enrich** | AI-powered lead enrichment with employee count, emails, LinkedIn, website analysis, and IQ scoring |
| **Personalize** | Claude generates personalized email content using recipient data, company research, and custom writing styles |
| **Outreach** | Multi-step email sequences with configurable delays, pause/resume, thread continuation, and dynamic recipient addition |
| **Track** | Open tracking (pixel), click tracking (URL rewriting), reply detection (Gmail polling), bounce detection |
| **Manage** | Full contact directory with tags, statuses, follow-ups, email history, and cold call scheduling |
| **Monitor** | Website change triggers, business signal detection, real estate listing monitoring |
| **Analyze** | AI-powered campaign insights, per-email scoring, subject line analysis, and actionable recommendations |

---

## Architecture

```
                    ┌─────────────────┐
                    │   React SPA     │
                    │   (Vite, :5174) │
                    └────────┬────────┘
                             │ HTTP / SSE
                    ┌────────▼────────┐
                    │   Flask API     │
                    │   (:5001)       │
                    └────────┬────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
   ┌──────▼──────┐   ┌──────▼──────┐   ┌──────▼──────┐
   │   SQLite    │   │  Gmail API  │   │  Claude API │
   │   (app.db)  │   │  (OAuth 2)  │   │ (Anthropic) │
   └─────────────┘   └─────────────┘   └─────────────┘
                             │
                    ┌────────▼────────┐
                    │  External APIs  │
                    │  Tavily, Google │
                    │  Places, Yelp   │
                    └─────────────────┘
```

- **Frontend**: Single-page React app served by Vite. Communicates with the backend via REST + Server-Sent Events (SSE) for real-time progress.
- **Backend**: Flask application with SQLAlchemy ORM. Background campaign execution via thread-safe runners. OAuth 2.0 for Gmail integration.
- **Database**: SQLite (file-based, `backend/data/app.db`). No external database server required.
- **AI**: Anthropic Claude API for email personalization, template generation, reply classification, and campaign insights.
- **External APIs**: Gmail API (sending/reading), Google Places API (map search), Yelp API (business search), Tavily API (web search/enrichment).

---

## Tech Stack

### Backend
| Technology | Purpose |
|---|---|
| Python / Flask | Web framework, API server |
| SQLAlchemy | ORM, database models |
| SQLite | Persistent storage |
| Google OAuth 2.0 | Gmail authentication |
| Gmail API | Email send/receive/thread management |
| Anthropic SDK | Claude AI integration |
| Tavily API | Web search and website analysis |
| Google Places API | Location-based prospect search |
| Yelp Fusion API | Business search and data |

### Frontend
| Technology | Purpose |
|---|---|
| React 19 | UI framework |
| Vite 7 | Build tool and dev server |
| React Router 7 | Client-side routing |
| Axios | HTTP client |
| React Quill | Rich text editor for email composition |

---

## Feature Inventory

### Command Center

**Home Dashboard** (`/`)
- Time-of-day greeting with AI-generated daily summary
- Action cards: Replies Waiting, Flagged for Review, Follow-ups Due, Leads to Review, Ready for Outreach
- Active campaign progress bars
- Key metrics: Emails Sent, Reply Rate, Pipeline Leads, Total Replies
- AI recommendation tip from latest campaign analysis
- Quick start guide for new users

**Daily Brief** (`/brief`)
- Summary for the current date
- Needs Attention items with links to relevant pages

---

### Prospect Discovery

**Map Explorer** (`/map-explorer`)
- Google Maps integration for location-based business search
- Address geocoding and radius-based nearby search
- Keyword search across Google Places and Yelp
- Filter by business type groups and minimum rating
- Add individual businesses or bulk-add to pipeline
- Multi-source data (Google, Yelp)

**Discovery** (`/discovery`)
- Automated prospect discovery criteria (search queries, zip codes, min rating, max results, scan interval)
- Run scans on demand or on schedule
- View discovered prospects with qualify/reject actions
- Add prospects to campaigns individually or in bulk
- Filter by rating and category
- Discovery statistics dashboard

**Prospects** (`/prospects`)
- Three-tab interface: Find, Review & Enrich, Ready
- **Find**: Recently added pipeline leads with links to Map Explorer and Discovery
- **Review & Enrich**: Search, filter, bulk enrich/approve/reject leads with IQ scoring
- **Ready**: Approved leads shown as cards with Quick Send capability

---

### Contact Management

**Contact Directory** (`/contacts`)
- Searchable directory of all contacts (name, email, company)
- Filter by tags (color-coded) and custom statuses
- Sort by name, company, status, last emailed, email count
- Inline status updates
- Follow-up tracking with overdue indicators
- Reply status indicators
- Pagination (50 per page)

**Contact Detail** (`/contacts/:id`)
- Editable profile: name, company, website
- Status management and tag assignment
- Follow-up scheduling with notes
- Complete email history table
- Cold call management
- Contact notes

**Cold Calls**
- Schedule cold call tasks with date, time, contact info, and notes
- Track call outcomes
- Integrated into contact detail and campaign detail views

---

### Email Campaigns

**Campaign List** (`/campaigns`)
- View all campaigns with status (draft, running, paused, completed, cancelled, failed)
- Create campaigns with name, optional template, and delay configuration
- Progress tracking (sent/total)
- Delete draft campaigns

**Campaign Detail** (`/campaigns/:id`)
- **Recipient Management**: Upload CSV with column mapping, preview recipients, add/remove/move recipients
- **AI Preview Generation**: Generate personalized email previews per recipient using Claude, with batch control
- **Approval Workflow**: Approve/reject individual or bulk recipients, edit previews inline, regenerate
- **Multi-Step Sequences**: Build email sequences with configurable delays between steps, per-step templates, per-step recipient management
- **Campaign Execution**: Start/pause/resume/cancel with real-time SSE progress streaming
- **Dynamic Addition**: Add contacts to running campaigns (directory, manual entry, or CSV bulk import)
- **Tracking**: Open/click/reply tracking per recipient
- **Export**: Download campaign results as CSV
- **Individual Send**: Send to specific recipients on demand

**Campaign Runner**
- Thread-safe background execution engine
- Configurable delay between emails
- Graceful pause/resume with state preservation
- Gmail thread continuation across sequence steps
- Dynamic recipient queue injection for mid-campaign additions
- Rate limiting and error handling

**Sequence Scheduler**
- Multi-step campaign orchestration
- Step-level send management
- Delay enforcement between steps
- Enrollment timing for staggered entry

---

### Quick Send

**Quick Send** (`/quick-send`)
- One-off personalized email generation and sending
- Recipient fields: email, name, company, website, research notes
- Optional template selection with dynamic custom fields
- Context/purpose input for AI guidance
- AI-generated subject and body with regeneration option
- Rich text editor for manual edits
- Attachment support
- Send-from selector for multi-account Gmail
- Recent email history with tracking status

Also available as a floating panel (FAB button on mobile, slide-out panel on desktop).

---

### Reply Hub

**Reply Inbox** (`/replies`)
- Centralized inbox for campaign reply management
- Filter: All, Needs Response, Flagged
- AI sentiment classification: Positive, Negative, Neutral
- AI response generation with refinement loop
- Send responses directly from Veloro
- Follow-up scheduling on replies
- Dismiss/archive replies
- Gmail account selector for multi-account setups

**Reply Autopilot**
- Configurable auto-response rules per sentiment type
- Auto-schedule follow-ups
- Human review keyword triggers
- Autopilot statistics

---

### Templates

**Template Manager** (`/templates`)
- Grid view of email templates (cards)
- Create/edit templates with subject and rich text body
- Template variables with `{{variable}}` syntax and fallback support (`{{city|state}}`)
- **AI Template Generation**: Generate from purpose, tone, audience, key points, CTA, and length parameters
- **AI Template Refinement**: Iterative feedback loop to refine generated templates
- **AI Template Enhancement**: Improve existing templates with AI
- Variable reference showing Core, Special, and Insights variable categories

---

### Pipeline Management

**Pipeline** (`/pipeline`)
- Lead database with statuses: New, Enriching, Enriched, Qualified, Approved, In Campaign, Rejected
- Search, sort, and filter leads
- Individual and bulk enrichment (employee count, emails, LinkedIn)
- IQ scoring with color-coded display (green >= 70, orange >= 40, red < 40)
- Approve leads with email selection and optional campaign assignment
- Bulk approve/reject operations
- Delete leads

---

### Insights & Analytics

**Insights** (`/insights`)
- AI-powered campaign performance analysis
- Analysis categories: Subject lines, Openings, Personalization depth, Email length, CTAs, Tone & Voice, What to avoid
- Campaign metadata: total sent, open rate, click rate, reply rate
- AI summary with top recommendations
- Per-email scoring with confidence levels (High, Medium, Low)
- Insight tiers: Winner, Middle, Low

---

### Listings Monitor

**Listings** (`/listings`)
- Monitor websites for new real estate/business listings
- Add monitored sites with configurable check intervals
- Manual check (per site or all sites)
- Filter by site, new only, price range, location, category
- Keyword search
- Quick-add listing form
- Email ingestion: parse broker emails for listing data
- Scan email alerts for listings
- Deal criteria configuration (price, type, location filters)
- Edit listing notes, mark as seen

---

### Triggers

**Triggers** (`/triggers`)
- Monitor websites for actionable events:
  - SSL certificate expiring
  - Website content changed
  - Review count/rating changed
  - Site down/unreachable
  - Copyright year outdated
- Severity levels: Critical, Important, Info
- Create outreach directly from triggers
- Dismiss triggers
- Check on demand
- Trigger statistics dashboard

---

### Signals

**Signals** (`/signals`)
- Monitor business intelligence signals:
  - Website changes
  - Job postings
  - News mentions
  - Funding events
  - Tech stack changes
- Signal source management
- Intent scoring (buying probability %)
- Relevance scoring (based on business profile keywords)
- Create outreach from signals
- Collect signals on demand
- Signal statistics

---

### Opportunity Feed

**Opportunities** (`/opportunities`)
- Unified feed aggregating Signals + Triggers + Discovery results
- Filter by source type
- Opportunity cards with business name, source, relevance score, intent score
- Create outreach from any opportunity
- Paginated feed

---

### Business Profile

**Business Profile** (`/business-profile`)
- Configure company identity: name, domain, tagline, description
- Define capabilities: service names, descriptions, keywords
- Set target market: industries, company sizes (1-10 to 1000+), geographies
- Relevance keywords that boost signal scoring
- Used by Veloro to match opportunities and score signal relevance

---

### Workspaces

- Multi-workspace support for managing separate projects/clients
- Workspace selector in the header
- All data (campaigns, contacts, templates, settings) scoped to active workspace
- Create, switch, and manage workspaces
- Persisted in localStorage with `X-Workspace-Id` header on every API request
- Feature visibility configurable per workspace

---

### Settings & Configuration

**Settings** (`/settings`)
- **Email Configuration**: Connect/disconnect Gmail accounts, set default sending account
- **API Keys**: Anthropic, Tavily, Google Places, Yelp, Tracking base URL
- **Writing Style**: Tone, opening style, value prop style, length, closing style, phrases to use/avoid, additional notes
- **Clay Integration**: Webhook setup, export configuration
- **Autopilot Configuration**: Enable/disable reply autopilot, per-sentiment auto-response rules, auto-scheduling, human review keywords
- **Feature Visibility**: Toggle features on/off per workspace (insights, replies, quick send, campaigns, templates, contacts, listings, cold calls)

---

## Project Structure

```
veloro/
├── backend/
│   ├── app.py                          # Flask entry point
│   ├── config.py                       # Configuration
│   ├── credentials.json                # Google OAuth credentials
│   ├── app/
│   │   ├── __init__.py                 # App factory, blueprint registration
│   │   ├── models/                     # SQLAlchemy models (25 models)
│   │   │   ├── business_profile.py     # Company identity & capabilities
│   │   │   ├── campaign.py             # Email campaigns
│   │   │   ├── campaign_step.py        # Multi-step sequence steps
│   │   │   ├── cold_call.py            # Cold call tasks
│   │   │   ├── contact.py              # Contact directory
│   │   │   ├── deal_criteria.py        # Listing deal filters
│   │   │   ├── discovery_criteria.py   # Automated discovery rules
│   │   │   ├── email_log.py            # Sent email records
│   │   │   ├── lead.py                 # Pipeline leads
│   │   │   ├── link_click.py           # Click tracking events
│   │   │   ├── listing.py              # Monitored listings
│   │   │   ├── monitored_site.py       # Websites to monitor
│   │   │   ├── open_event.py           # Email open tracking events
│   │   │   ├── recipient.py            # Campaign recipients
│   │   │   ├── reply_message.py        # Incoming replies
│   │   │   ├── settings.py             # Workspace settings (key-value)
│   │   │   ├── signal.py               # Business signals
│   │   │   ├── signal_source.py        # Signal source configs
│   │   │   ├── step_recipient.py       # Per-step recipient state
│   │   │   ├── tag.py                  # Contact tags
│   │   │   ├── template.py             # Email templates
│   │   │   ├── website_analysis_log.py # Website analysis cache
│   │   │   ├── website_trigger.py      # Website trigger events
│   │   │   └── workspace.py            # Workspaces
│   │   │
│   │   ├── routes/                     # API blueprints (23 route files)
│   │   │   ├── attachments.py          # File upload/management
│   │   │   ├── auth.py                 # Gmail OAuth, API key status
│   │   │   ├── brief.py                # Daily brief
│   │   │   ├── campaigns.py            # Campaign CRUD & execution
│   │   │   ├── clay.py                 # Clay integration
│   │   │   ├── cold_calls.py           # Cold call management
│   │   │   ├── contacts.py             # Contact directory
│   │   │   ├── discovery.py            # Prospect discovery
│   │   │   ├── features.py             # Feature visibility
│   │   │   ├── insights.py             # Performance insights
│   │   │   ├── listings.py             # Listing monitor
│   │   │   ├── map_explorer.py         # Map search
│   │   │   ├── opportunities.py        # Opportunity feed
│   │   │   ├── pipeline.py             # Lead pipeline
│   │   │   ├── profile.py              # Business profile
│   │   │   ├── quick_send.py           # One-off emails
│   │   │   ├── replies.py              # Reply inbox
│   │   │   ├── signals.py              # Signals
│   │   │   ├── templates.py            # Template management
│   │   │   ├── tracking.py             # Open/click tracking
│   │   │   ├── triggers.py             # Website triggers
│   │   │   └── workspaces.py           # Workspace management
│   │   │
│   │   └── services/                   # Business logic (35 service files)
│   │       ├── business_search.py      # Business search aggregation
│   │       ├── calendar_service.py     # Calendar integration
│   │       ├── campaign_runner.py      # Campaign execution engine
│   │       ├── category_normalizer.py  # Listing category normalization
│   │       ├── claude_service.py       # Anthropic Claude integration
│   │       ├── clay_export.py          # Clay data export
│   │       ├── competitor_discovery.py # Competitor analysis
│   │       ├── confidence_scorer.py    # AI confidence scoring
│   │       ├── csv_parser.py           # CSV import parsing
│   │       ├── email_alert_scanner.py  # Email alert scanning
│   │       ├── email_insights.py       # Campaign performance analysis
│   │       ├── email_listing_parser.py # Listing extraction from emails
│   │       ├── email_scoring.py        # Per-email quality scoring
│   │       ├── enrichment_service.py   # Lead enrichment
│   │       ├── feature_service.py      # Feature visibility logic
│   │       ├── generation_runner.py    # AI preview generation
│   │       ├── gmail_service.py        # Gmail API wrapper
│   │       ├── listing_scraper.py      # Website listing scraper
│   │       ├── places_service.py       # Google Places API
│   │       ├── profile_service.py      # Business profile service
│   │       ├── prospect_discovery.py   # Automated prospect finding
│   │       ├── recipient_addition.py   # Dynamic recipient addition
│   │       ├── reply_autopilot.py      # Automated reply handling
│   │       ├── reply_checker.py        # Gmail reply detection
│   │       ├── sequence_scheduler.py   # Multi-step sequence orchestration
│   │       ├── signal_engine.py        # Signal detection engine
│   │       ├── spam_checker.py         # Spam detection
│   │       ├── step_runner.py          # Sequence step execution
│   │       ├── tracking_service.py     # Open/click tracking
│   │       ├── trigger_monitor.py      # Website trigger monitoring
│   │       ├── web_search.py           # Tavily web search
│   │       ├── website_analyzer.py     # Website content analysis
│   │       ├── website_insights.py     # Website insight extraction
│   │       └── yelp_service.py         # Yelp API integration
│   │
│   └── data/
│       └── app.db                      # SQLite database
│
└── frontend/
    ├── package.json
    ├── vite.config.js
    ├── index.html
    └── src/
        ├── App.jsx                     # Root component, routing, navigation
        ├── main.jsx                    # Entry point
        ├── api/
        │   └── client.js              # Axios API client (100+ API functions)
        ├── hooks/
        │   └── useFeatureVisibility.js # Per-workspace feature toggle hook
        ├── components/
        │   ├── AddContactToRunningCampaignModal.jsx
        │   ├── AttachmentPicker.jsx
        │   ├── BulkAddProgress.jsx
        │   ├── ColdCallModal.jsx
        │   ├── ConfirmDialog.jsx
        │   ├── ContactDirectoryPicker.jsx
        │   ├── MobileLayout.jsx
        │   ├── QuickSendPanel.jsx
        │   ├── RichTextEditor.jsx
        │   ├── SequenceBuilder.jsx
        │   ├── StepRecipientList.jsx
        │   ├── Toast.jsx
        │   ├── WorkspaceSelector.jsx
        │   └── ui/
        │       ├── PageHeader.jsx
        │       └── TabBar.jsx
        └── pages/
            ├── Home.jsx
            ├── BusinessProfile.jsx
            ├── Campaigns.jsx
            ├── CampaignDetail.jsx
            ├── Contacts.jsx
            ├── ContactDetail.jsx
            ├── DailyBrief.jsx
            ├── Discovery.jsx
            ├── Insights.jsx
            ├── Listings.jsx
            ├── MapExplorer.jsx
            ├── OpportunityFeed.jsx
            ├── Pipeline.jsx
            ├── Prospects.jsx
            ├── QuickSend.jsx
            ├── ReplyHub.jsx
            ├── Settings.jsx
            ├── Signals.jsx
            ├── Templates.jsx
            └── Triggers.jsx
```

---

## Data Models

| Model | Table | Purpose |
|---|---|---|
| Workspace | `workspaces` | Multi-tenant workspace isolation |
| WorkspaceSettings | `workspace_settings` | Key-value settings per workspace |
| BusinessProfile | `business_profiles` | Company identity, capabilities, target market |
| Campaign | `campaigns` | Email campaigns with status, config, tracking |
| CampaignStep | `campaign_steps` | Steps in multi-step sequences |
| Template | `templates` | Reusable email templates with variables |
| Recipient | `recipients` | Campaign recipients with preview/approval state |
| StepRecipient | `step_recipients` | Per-step recipient state for sequences |
| EmailLog | `email_logs` | Record of every sent email |
| OpenEvent | `open_events` | Tracking pixel open events |
| LinkClick | `link_clicks` | Click tracking events |
| ReplyMessage | `reply_messages` | Incoming email replies |
| Contact | `contacts` | Contact directory entries |
| Tag | `tags` | Contact tags (many-to-many via `contact_tags`) |
| ColdCall | `cold_calls` | Cold call scheduling and outcomes |
| Lead | `leads` | Pipeline leads with enrichment data |
| DiscoveryCriteria | `discovery_criteria` | Automated prospect search rules |
| MonitoredSite | `monitored_sites` | Websites to monitor for listings |
| Listing | `listings` | Discovered listings |
| DealCriteria | `deal_criteria` | Listing intake filters |
| WebsiteTrigger | `website_triggers` | Detected website trigger events |
| Signal | `signals` | Business intelligence signals |
| SignalSource | `signal_sources` | Signal monitoring configurations |
| WebsiteAnalysisLog | `website_analysis_logs` | Cached website analysis results |

---

## Backend Services

### Campaign Execution
| Service | Purpose |
|---|---|
| `CampaignRunner` | Thread-safe campaign execution engine with pause/resume, rate limiting, and dynamic recipient injection |
| `StepRunner` | Executes individual sequence steps with Gmail thread continuation |
| `SequenceScheduler` | Orchestrates multi-step sequences with delay enforcement |
| `GenerationRunner` | AI preview generation with SSE progress streaming |
| `RecipientAddition` | Dynamic recipient addition to running campaigns |

### AI & Personalization
| Service | Purpose |
|---|---|
| `ClaudeService` | Anthropic Claude API wrapper for all AI operations |
| `EmailInsights` | AI-powered campaign performance analysis |
| `EmailScoring` | Per-email quality scoring with confidence levels |
| `ConfidenceScorer` | AI confidence assessment |
| `SpamChecker` | Spam likelihood detection |

### Email & Communication
| Service | Purpose |
|---|---|
| `GmailService` | Gmail API: send, read, thread management, OAuth multi-account |
| `TrackingService` | Open pixel injection, URL rewriting for click tracking |
| `ReplyChecker` | Gmail polling for reply detection |
| `ReplyAutopilot` | Automated reply handling with sentiment-based rules |

### Prospect Discovery & Enrichment
| Service | Purpose |
|---|---|
| `PlacesService` | Google Places API integration |
| `YelpService` | Yelp Fusion API integration |
| `BusinessSearch` | Multi-source business search aggregation |
| `ProspectDiscovery` | Automated prospect finding based on criteria |
| `CompetitorDiscovery` | Competitor analysis |
| `EnrichmentService` | Lead enrichment (employees, emails, LinkedIn, website) |
| `WebSearch` | Tavily web search integration |
| `WebsiteAnalyzer` | Website content analysis |
| `WebsiteInsights` | Website insight extraction for personalization |

### Monitoring
| Service | Purpose |
|---|---|
| `TriggerMonitor` | Website change detection (SSL, content, reviews, uptime, copyright) |
| `SignalEngine` | Business signal detection (jobs, news, funding, tech stack) |
| `ListingScraper` | Website scraping for listings |
| `EmailAlertScanner` | Email inbox scanning for listing alerts |
| `EmailListingParser` | Extract listing data from broker emails |
| `CategoryNormalizer` | Listing category standardization |

### Integration & Export
| Service | Purpose |
|---|---|
| `ClayExport` | Clay platform data export |
| `CsvParser` | CSV import parsing with column mapping |
| `CalendarService` | Calendar integration |
| `ProfileService` | Business profile management |
| `FeatureService` | Per-workspace feature visibility |

---

## API Surface

The backend exposes **100+ REST endpoints** across 23 route blueprints. Key endpoint groups:

| Blueprint | Base Path | Endpoints | Purpose |
|---|---|---|---|
| Auth | `/auth` | 4 | Gmail OAuth flow, API key status |
| Campaigns | `/api/campaigns` | 20+ | Full campaign lifecycle CRUD, recipients, steps, execution |
| Templates | `/api/templates` | 8 | Template CRUD, AI generation, variables |
| Contacts | `/api/contacts` | 10 | Contact directory CRUD, tags, statuses |
| Replies | `/api/replies` | 8 | Reply inbox, AI classification, response generation |
| Pipeline | `/api/pipeline` | 10 | Lead management, enrichment, approval |
| Discovery | `/api/discovery` | 8 | Discovery criteria, prospect management |
| Map Explorer | `/api/map` | 6 | Geocoding, place search, pipeline add |
| Quick Send | `/api/quick-send` | 3 | One-off email generation and sending |
| Listings | `/api/listings` | 15 | Site monitoring, listing management, email ingestion |
| Triggers | `/api/triggers` | 6 | Trigger monitoring and management |
| Signals | `/api/signals` | 8 | Signal detection and source management |
| Opportunities | `/api/opportunities` | 2 | Unified opportunity feed |
| Insights | `/api/insights` | 3 | Performance analysis and email scoring |
| Tracking | `/api/tracking` | 3 | Open pixel, click redirect, reply check |
| Workspaces | `/api/workspaces` | 5 | Workspace CRUD |
| Features | `/api/features` | 3 | Feature visibility management |
| Profile | `/api/profile` | 2 | Business profile CRUD |
| Cold Calls | `/api/cold-calls` | 5 | Cold call CRUD and outcomes |
| Attachments | `/api/attachments` | 2 | File upload/delete |
| Clay | `/api/clay` | 4 | Clay integration and export |
| Brief | `/api/brief` | 1 | Daily summary |

**Real-time**: Campaign progress and preview generation use Server-Sent Events (SSE) for live updates.

---

## Setup & Configuration

### Prerequisites
- Python 3.10+
- Node.js 18+
- Google Cloud project with Gmail API enabled
- Anthropic API key

### 1. Backend Setup
```bash
cd backend
pip install -r requirements.txt
python app.py
```
Backend runs at `http://localhost:5001`

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Frontend runs at `http://localhost:5174`

### 3. Gmail API Configuration
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project and enable the Gmail API
3. Create OAuth 2.0 credentials (Web application type)
4. Add redirect URI: `http://localhost:5001/auth/gmail/callback`
5. Download `credentials.json` to `backend/` folder
6. Add your email as a test user in the OAuth consent screen

### 4. API Keys
Configure via the Settings page (`/settings`):
- **Anthropic API Key** (required) - for Claude AI personalization
- **Tavily API Key** (optional) - for web search enrichment
- **Google Places API Key** (optional) - for Map Explorer
- **Yelp API Key** (optional) - for Yelp business search

---

## Strategic Positioning

### Defensible Value (Real Moat)
- **Campaign orchestration engine**: Thread-safe background processing, multi-step sequences, configurable delays, Gmail thread continuation, graceful pause/resume (~2,000+ lines of workflow logic)
- **Email tracking infrastructure**: Pixel-based opens, URL rewriting for clicks, reply detection via Gmail polling, bounce detection
- **Gmail API integration depth**: OAuth multi-account, thread ID management, rate limiting, error handling
- **Contact pipeline / CRM**: Pipeline status management, follow-up scheduling, email history, workspace isolation
- **Accumulated data**: Campaign performance data, contact histories, template effectiveness compound over time

### Competitive Landscape
- Primary competitors are established outreach SaaS platforms (Instantly, Smartlead, Apollo, Lemlist) at $100-300/mo
- Veloro differentiates via: self-hosted (no per-seat fees), Claude-powered personalization, full data control, customizable workflows

### Key Insight
AI model improvements make the platform *better*, not obsolete. Claude is an ingredient, not the product. The product is the workflow: upload 500 founders from CSV, run a 3-step sequence with AI personalization, track opens/clicks/replies, auto-pause on bounce, continue in the same Gmail thread.

---

## Roadmap

### Implemented: Add Contacts to Running Campaigns
Add new contacts to campaigns mid-execution via directory selection, manual entry, or CSV bulk import. New contacts start at step 1 with proper enrollment timing.

### Implemented: Workspace Feature Visibility
Per-workspace feature toggling so different workspaces can show/hide features (e.g., hide Listings for a business outreach workspace). Admin-only controls with data preservation.

### Future Opportunities
- Conditional branching (if opened but didn't reply, send variant B)
- A/B testing for subject lines and email content
- Time-of-day send optimization
- Email warmup and domain rotation
- Sending reputation monitoring
- CRM sync integrations
- Calendar booking link integration
- Slack notifications on replies
