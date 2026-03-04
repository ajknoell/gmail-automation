# Veloro

A web application for automating email outreach campaigns with AI-powered personalization using Claude.

## Features

- **CSV/Excel Import**: Upload recipient lists with name, email, company, and custom fields
- **Email Templates**: Create reusable templates with variable placeholders
- **AI Personalization**: Use Claude to personalize each email based on recipient data
- **Campaign Management**: Track sent, pending, and failed emails
- **Bulk Sending**: Send with configurable delays, pause/resume controls
- **Real-time Progress**: Watch campaign progress with live updates
- **Export Results**: Download campaign results as CSV

## Quick Start

### 1. Start the Backend

```bash
cd backend
python app.py
```

Backend runs at http://localhost:5001

### 2. Start the Frontend

```bash
cd frontend
npm install  # First time only
npm run dev
```

Frontend runs at http://localhost:5173

### 3. Configure Settings

1. Open http://localhost:5173/settings
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
│   ├── app.py              # Flask entry point
│   ├── config.py           # Configuration
│   ├── credentials.json    # Google OAuth credentials
│   ├── app/
│   │   ├── models/         # Database models
│   │   ├── routes/         # API endpoints
│   │   └── services/       # Business logic
│   └── data/
│       └── app.db          # SQLite database
│
└── frontend/
    ├── src/
    │   ├── api/            # API client
    │   ├── components/     # React components
    │   └── pages/          # Page components
    └── package.json
```

## Code Quality

Veloro uses a continuous code review system powered by Claude Code hooks and automated linting.

### Automated Review (Claude Code Hooks)

When using Claude Code, every file edit automatically triggers quality checks:
- **Python files**: Linted with [ruff](https://docs.astral.sh/ruff/) for style, security, and bug detection
- **JavaScript/JSX files**: Linted with ESLint with React hooks and refresh plugins

These hooks are defined in `.claude/settings.json` and run transparently after each edit.

### On-Demand Review

Run a full project review at any time:

```bash
./scripts/review.sh
```

### Quality Standards

See [CLAUDE.md](CLAUDE.md) for the complete code review checklist including:
- Python type annotation and docstring requirements
- Security review checklist (SSRF, SQL injection, XSS, secrets)
- Performance review checklist (N+1 queries, pagination, async)
- Architecture guidelines for models, routes, and services

## Usage

### Creating a Campaign

1. **Create a Template**: Go to Templates, create an email template with variables like `{{name}}`, `{{company}}`
2. **Create a Campaign**: Go to Campaigns, create a new campaign and select your template
3. **Upload Recipients**: Upload a CSV/Excel file with columns: email, name, company
4. **Generate Previews**: Click "Generate AI Previews" to personalize emails with Claude
5. **Review & Approve**: Review personalized emails and approve them
6. **Start Sending**: Click "Start Campaign" to begin sending

### CSV Format Example

```csv
email,name,company
john@example.com,John Smith,Acme Corp
jane@example.com,Jane Doe,Tech Inc
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /auth/status` | Check Gmail/API connection status |
| `GET /auth/gmail/connect` | Start Gmail OAuth flow |
| `CRUD /api/templates` | Manage email templates |
| `CRUD /api/campaigns` | Manage campaigns |
| `POST /api/campaigns/:id/upload` | Upload recipients |
| `POST /api/campaigns/:id/start` | Start sending |
| `POST /api/campaigns/:id/pause` | Pause campaign |
| `POST /api/campaigns/:id/resume` | Resume campaign |
| `GET /api/campaigns/:id/progress` | Real-time progress (SSE) |
| `GET /api/campaigns/:id/export` | Export results CSV |

## Tech Stack

- **Frontend**: React, Vite, React Router
- **Backend**: Flask, SQLAlchemy, SQLite
- **APIs**: Gmail API, Anthropic Claude API
