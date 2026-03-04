# Veloro

A B2B sales automation platform with AI-powered email campaigns, prospect discovery, pipeline management, and signal monitoring. Built with Flask and React.

## Features

### Outreach & Campaigns
- **Multi-step Email Campaigns** — Sequences with configurable delays, A/B testing variants, pause/resume controls
- **AI Personalization** — Claude generates personalized email copy per recipient with confidence scoring
- **Quick Send** — One-off emails outside of campaigns
- **Email Templates** — Reusable templates with variable placeholders (`{{name}}`, `{{company}}`, etc.)
- **Reply Management** — Threaded reply hub with sentiment analysis and auto-response autopilot
- **Email Tracking** — Open/click/reply tracking via pixel and link rewriting
- **Attachments** — File attachments on campaign emails
- **Add Contacts to Running Campaigns** — Directory selection, manual entry, or bulk CSV import into active campaigns

### Prospecting & Discovery
- **Prospect Discovery** — Automated scanning for new prospects based on configurable criteria
- **Map Explorer** — Geographic business search via Google Places integration
- **Listings Monitor** — Scrapes and monitors business listings (e.g., real estate, job boards)
- **Cold Call Tracking** — Log and track cold call outcomes
- **Clay Integration** — Export contacts to Clay for enrichment
- **Lead Enrichment** — Background worker enriches leads with business data

### Pipeline & CRM
- **Contact Directory** — Full contact management with tags, status tracking, follow-up scheduling
- **Pipeline** — Deal pipeline with stage management
- **Opportunity Feed** — Aggregated view of sales opportunities

### Intelligence & Signals
- **Signal Engine** — Monitors configurable signal sources and surfaces buying signals
- **Website Triggers** — Monitors websites for changes and triggers actions
- **Daily Brief** — AI-generated daily summary of key activities and signals
- **Email Insights** — Campaign performance analytics and engagement metrics
- **Business Profiles** — Company profile pages with aggregated data

### Platform
- **Multi-workspace** — Isolated workspaces with independent data, settings, and feature toggles
- **Feature Visibility** — Per-workspace feature toggles to show/hide modules
- **Settings** — Gmail OAuth, API keys, writing style, workspace configuration

## Quick Start

### 1. Start the Backend

```bash
cd backend
python app.py
```

Backend runs at http://localhost:5001. Seven background services start automatically:
- Reply checker (every 5 min)
- Sequence scheduler (every 5 min)
- Listing monitor (hourly)
- Prospect scanner (hourly)
- Signal engine (hourly)
- Enrichment worker (every 10 min)
- Trigger monitor (daily)

### 2. Start the Frontend

```bash
cd frontend
npm install  # First time only
npm run dev
```

Frontend runs at http://localhost:5174

### 3. Configure Settings

1. Open http://localhost:5174/settings
2. Click "Connect Gmail Account" and authorize
3. Enter your Anthropic API key

## Setup Requirements

### Gmail API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable Gmail API
4. Create OAuth 2.0 credentials (Web application type)
5. Add redirect URI: `http://localhost:5001/auth/gmail/callback`
6. Download `credentials.json` to `backend/` folder
7. Add your email as a test user in OAuth consent screen

### Anthropic API

1. Go to [Anthropic Console](https://console.anthropic.com/)
2. Create an API key
3. Enter in the Settings page

## Project Structure

```
veloro/
├── backend/
│   ├── app.py                    # Flask entry point
│   ├── config.py                 # Configuration
│   ├── credentials.json          # Google OAuth credentials
│   ├── app/
│   │   ├── __init__.py           # App factory, blueprint registration, migrations, background services
│   │   ├── models/               # 25 SQLAlchemy models
│   │   │   ├── campaign.py       # Campaign, with workspace scoping
│   │   │   ├── campaign_step.py  # Multi-step sequences, A/B variants
│   │   │   ├── recipient.py      # Campaign recipients with confidence scoring
│   │   │   ├── step_recipient.py # Per-step recipient state
│   │   │   ├── email_log.py      # Sent email records with tracking
│   │   │   ├── contact.py        # Contact directory entries
│   │   │   ├── tag.py            # Contact tags
│   │   │   ├── template.py       # Email templates
│   │   │   ├── reply_message.py  # Reply threads with sentiment
│   │   │   ├── open_event.py     # Email open tracking events
│   │   │   ├── link_click.py     # Link click tracking events
│   │   │   ├── listing.py        # Monitored business listings
│   │   │   ├── monitored_site.py # Listing source sites
│   │   │   ├── lead.py           # Enriched leads
│   │   │   ├── cold_call.py      # Cold call records
│   │   │   ├── signal.py         # Buying signals
│   │   │   ├── signal_source.py  # Signal source configuration
│   │   │   ├── discovery_criteria.py # Prospect discovery rules
│   │   │   ├── deal_criteria.py  # Deal qualification criteria
│   │   │   ├── website_trigger.py    # Website change triggers
│   │   │   ├── website_analysis_log.py # Website analysis results
│   │   │   ├── business_profile.py   # Company profiles
│   │   │   ├── workspace.py      # Workspace definitions
│   │   │   └── settings.py       # Global + workspace settings
│   │   ├── routes/               # 22 Flask blueprints
│   │   │   ├── auth.py           # Gmail OAuth + API key management
│   │   │   ├── campaigns.py      # Campaign CRUD, steps, sending, recipient addition
│   │   │   ├── templates.py      # Email template management
│   │   │   ├── contacts.py       # Contact directory + tags
│   │   │   ├── replies.py        # Reply hub + sentiment
│   │   │   ├── quick_send.py     # One-off email sending
│   │   │   ├── tracking.py       # Open/click pixel + link tracking
│   │   │   ├── insights.py       # Email analytics
│   │   │   ├── pipeline.py       # Deal pipeline
│   │   │   ├── opportunities.py  # Opportunity feed
│   │   │   ├── signals.py        # Signal management
│   │   │   ├── discovery.py      # Prospect discovery criteria + results
│   │   │   ├── listings.py       # Listing CRUD + monitoring
│   │   │   ├── map_explorer.py   # Google Places search
│   │   │   ├── cold_calls.py     # Cold call logging
│   │   │   ├── triggers.py       # Website trigger rules
│   │   │   ├── brief.py          # Daily brief generation
│   │   │   ├── clay.py           # Clay export integration
│   │   │   ├── profile.py        # Business profile pages
│   │   │   ├── features.py       # Feature visibility toggles
│   │   │   ├── workspaces.py     # Workspace CRUD
│   │   │   └── attachments.py    # File attachment handling
│   │   └── services/             # 35+ business logic services
│   │       ├── campaign_runner.py    # Campaign send orchestration
│   │       ├── step_runner.py        # Per-step execution
│   │       ├── sequence_scheduler.py # Follow-up step scheduling
│   │       ├── generation_runner.py  # AI content generation
│   │       ├── claude_service.py     # Anthropic Claude API client
│   │       ├── gmail_service.py      # Gmail API client
│   │       ├── reply_checker.py      # Background reply polling
│   │       ├── reply_autopilot.py    # Automated reply handling
│   │       ├── tracking_service.py   # Open/click tracking
│   │       ├── enrichment_service.py # Lead enrichment worker
│   │       ├── prospect_discovery.py # Prospect scanner
│   │       ├── signal_engine.py      # Signal detection
│   │       ├── trigger_monitor.py    # Website change detection
│   │       ├── listing_scraper.py    # Listing scraper + monitor
│   │       ├── website_analyzer.py   # Website content analysis
│   │       ├── confidence_scorer.py  # Email confidence scoring
│   │       ├── feature_service.py    # Feature visibility logic
│   │       ├── recipient_addition.py # Add contacts to running campaigns
│   │       ├── csv_parser.py         # CSV/Excel import
│   │       └── ...                   # + more specialized services
│   └── data/
│       └── app.db                # SQLite database
│
└── frontend/
    ├── src/
    │   ├── api/client.js         # API client (all endpoint functions)
    │   ├── pages/                # 20 page components
    │   │   ├── Home.jsx          # Dashboard
    │   │   ├── Campaigns.jsx     # Campaign list
    │   │   ├── CampaignDetail.jsx # Campaign detail + step management
    │   │   ├── Templates.jsx     # Template editor
    │   │   ├── Contacts.jsx      # Contact directory
    │   │   ├── ContactDetail.jsx # Contact detail page
    │   │   ├── ReplyHub.jsx      # Reply management
    │   │   ├── QuickSend.jsx     # Quick email send
    │   │   ├── Insights.jsx      # Analytics dashboard
    │   │   ├── Pipeline.jsx      # Deal pipeline
    │   │   ├── OpportunityFeed.jsx # Opportunities
    │   │   ├── Signals.jsx       # Signal feed
    │   │   ├── Discovery.jsx     # Prospect discovery
    │   │   ├── Prospects.jsx     # Prospect list
    │   │   ├── Listings.jsx      # Listing management
    │   │   ├── MapExplorer.jsx   # Map-based search
    │   │   ├── Triggers.jsx      # Website triggers
    │   │   ├── DailyBrief.jsx    # Daily brief
    │   │   ├── BusinessProfile.jsx # Company profiles
    │   │   └── Settings.jsx      # Settings + feature toggles
    │   ├── components/           # Shared components
    │   │   ├── SequenceBuilder.jsx           # Multi-step campaign builder
    │   │   ├── AddContactToRunningCampaignModal.jsx # Add contacts modal
    │   │   ├── ContactDirectoryPicker.jsx    # Contact selection
    │   │   ├── RichTextEditor.jsx            # Quill-based editor
    │   │   ├── WorkspaceSelector.jsx         # Workspace switcher
    │   │   ├── MobileLayout.jsx              # Mobile responsive layout
    │   │   └── ...
    │   ├── hooks/
    │   │   └── useFeatureVisibility.js  # Feature toggle hook
    │   └── main.jsx
    └── package.json
```

## Tech Stack

- **Frontend**: React 19, Vite, React Router, Axios, React Quill
- **Backend**: Flask, SQLAlchemy, SQLite, Playwright (scraping), openpyxl (Excel), Pillow (images)
- **APIs**: Gmail API (OAuth), Anthropic Claude API, Google Places API
- **Background**: 7 auto-starting pollers for reply checking, scheduling, discovery, monitoring, enrichment, and signal detection
