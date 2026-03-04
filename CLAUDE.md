# Veloro - Project Instructions for Claude

## Project Overview

Veloro is a Flask + React application for AI-powered email outreach automation.
- Backend: Python/Flask with SQLAlchemy (SQLite), located in `backend/`
- Frontend: React 19 with Vite, located in `frontend/`
- API pattern: Flask Blueprints with routes in `backend/app/routes/`, business logic in `backend/app/services/`, models in `backend/app/models/`

## Continuous Code Review

You are a code review agent. After EVERY code change you make, you MUST silently verify that the change meets ALL of the following quality standards before presenting it. If it does not, fix it before showing it to the user.

### Python Backend Standards

1. **Type annotations**: All function signatures must include type hints for parameters and return types.
   ```python
   # Good
   def get_campaign(campaign_id: int) -> dict:

   # Bad
   def get_campaign(campaign_id):
   ```

2. **Docstrings**: Every function and class must have a docstring. Route handlers need at minimum a one-line description.

3. **Error handling**: Never use bare `except:` or `except Exception: pass`. Always log the exception or handle it specifically.
   ```python
   # Good
   except ValueError as e:
       logger.warning(f"Invalid input: {e}")
       return jsonify({"error": str(e)}), 400

   # Bad
   except Exception:
       pass
   ```

4. **No hardcoded secrets**: Configuration values must come from environment variables or config files, never inline strings.

5. **Input validation**: All API endpoints must validate input data before processing. Return 400 with a clear error message for invalid input.

6. **SQL injection prevention**: Always use parameterized queries or SQLAlchemy ORM. Never use string formatting for SQL.

7. **File size**: If a file exceeds 300 lines, consider whether it should be split into smaller modules. Flag this to the user.

8. **DRY principle**: Before writing new code, check if similar functionality already exists in the codebase. Common patterns:
   - Email sending: `backend/app/services/gmail_service.py`
   - Claude API calls: `backend/app/services/claude_service.py`
   - CSV parsing: `backend/app/services/csv_parser.py`
   - Campaign orchestration: `backend/app/services/campaign_runner.py`, `step_runner.py`, `sequence_scheduler.py`

9. **Import organization**: Standard library, then third-party, then local imports, each group separated by a blank line.

### React Frontend Standards

1. **Component size**: Components exceeding 300 lines should be broken into smaller sub-components.

2. **Error boundaries**: API calls must have error handling with user-visible feedback.

3. **No console.log in production code**: Use it for debugging only; remove before committing.

4. **Prop validation**: Document expected props clearly.

5. **useEffect cleanup**: Effects that set up listeners or timers must return a cleanup function. Existing pattern in `frontend/src/hooks/useFeatureVisibility.js` is a good reference.

6. **API client pattern**: All API calls go through `frontend/src/api/client.js`. Never use `axios` or `fetch` directly in components.

7. **CSS**: All styles go in `App.css`. Follow existing class naming conventions (kebab-case).

### Security Review Checklist

For every change, verify:
- No API keys, tokens, or passwords in code
- No SSRF vulnerabilities (validate/sanitize URLs before fetching)
- No SQL injection (use ORM or parameterized queries)
- No XSS (React auto-escapes, but watch for dangerouslySetInnerHTML)
- No path traversal in file operations
- Proper CORS configuration maintained
- Input validated and sanitized on backend

### Performance Review Checklist

For every change, verify:
- No N+1 query patterns (use eager loading or join queries)
- No unnecessary database queries in loops
- Large lists paginated
- Background tasks for long-running operations
- No blocking operations in request handlers

### Architecture Guidelines

- **Models**: Thin models with `to_dict()` serialization. Keep business logic in services.
- **Routes**: Route handlers should validate input, call a service, and return JSON. Keep them under 50 lines.
- **Services**: Business logic lives here. Services should be stateless where possible.
- **Frontend pages**: Container components that fetch data and pass to presentational components.

## Existing Technical Debt to Address Incrementally

When working near these areas, improve them opportunistically:
- `backend/app/services/claude_service.py` (2,357 lines) -- should be split into focused modules
- `backend/app/routes/campaigns.py` (1,974 lines) -- route handlers too large, extract to services
- `frontend/src/pages/CampaignDetail.jsx` (1,830 lines) -- break into sub-components
- `frontend/src/pages/Listings.jsx` (2,513 lines) -- break into sub-components
- `backend/app/__init__.py` (547 lines) -- migration logic should be extracted to a migrations module

## Commands

- Backend: `cd backend && python app.py` (runs on port 5001)
- Frontend: `cd frontend && npm run dev` (runs on port 5174)
- Frontend lint: `cd frontend && npm run lint`
- Backend lint: `cd backend && ruff check .`
- Full review: `./scripts/review.sh`
