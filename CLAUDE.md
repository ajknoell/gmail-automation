# Veloro - Development Guidelines

## Overview

Veloro is a B2B sales automation platform built with Flask (backend) and React/Vite (frontend). It handles email campaign orchestration, prospect discovery, pipeline management, signal monitoring, and AI-powered personalization via Claude.

## Running the App

```bash
# Backend (port 5001)
cd backend && python app.py

# Frontend (port 5174)
cd frontend && npm run dev
```

The frontend proxies `/api` and `/auth` routes to the backend. Seven background services start automatically with the backend (reply checker, listing monitor, sequence scheduler, prospect scanner, trigger monitor, enrichment worker, signal engine).

## Architecture

- **Multi-workspace**: All data is scoped by `workspace_id`. The `X-Workspace-Id` header resolves the active workspace per request.
- **Feature visibility**: Features can be toggled per workspace via `WorkspaceSettings` flags. The frontend uses the `useFeatureVisibility` hook to conditionally render navigation and routes.
- **Background services**: Pollers run on configurable intervals (see `__init__.py`). They handle reply checking, sequence scheduling, prospect discovery, listing scraping, trigger monitoring, lead enrichment, and signal detection.
- **Database**: SQLite via SQLAlchemy. Migrations run inline in `_run_migrations()` on startup — no Alembic.

## Documentation Rules

**When you add or modify code, update `README.md` to reflect the change.** Specifically:

- **New feature/module**: Add it to the Features section under the appropriate category.
- **New page/route**: Update the Project Structure section if it introduces a new page or major component.
- **Tech stack change**: Add new significant dependencies to the Tech Stack section.
- **Configuration change**: Update Quick Start or Setup sections if setup steps change.

Keep plan files (PLAN.md, etc.) updated with implementation status when completing planned features.

## Key Directories

```
backend/
  app/models/       # 25 SQLAlchemy models
  app/routes/       # 22 Flask blueprints
  app/services/     # 35+ business logic services
  data/             # SQLite DB + uploads

frontend/src/
  pages/            # 20 page components
  components/       # Shared UI components
  hooks/            # Custom React hooks
  api/client.js     # API client functions
```

## Conventions

- Route blueprints are registered in `app/__init__.py` with `/api/<name>` prefixes
- Models use `to_dict()` for JSON serialization
- Frontend API calls go through `frontend/src/api/client.js`
- Workspace scoping is handled via `g.workspace_id` in Flask and the `X-Workspace-Id` header from the frontend
