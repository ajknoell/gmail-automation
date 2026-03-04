# Prospect & Email Scoring Systems

This document describes every scoring system used in the application, including the factors, weights, thresholds, and how each score feeds into downstream workflows.

---

## 1. Lead Quality Score (0–100)

**Source:** `backend/app/services/enrichment_service.py` — `EnrichmentService.calculate_score()`

Measures how complete and promising a lead's data profile is. Calculated after enrichment and stored on the `Lead` model as `score` with a `score_breakdown` JSON field.

### Scoring Factors

| Factor | Condition | Points |
|---|---|---|
| Website | Lead has a website URL | +15 |
| Phone | Lead has a phone number | +10 |
| Email | Lead has at least one discovered email | +20 |
| Employee count known | `employee_count` is populated | +10 |
| Employee sweet spot | `employee_count` between 5–200 | +10 |
| High Google rating | `google_rating` >= 4.0 | +10 |
| Review count | `review_count` >= 10 | +10 |
| LinkedIn | Lead has a LinkedIn URL | +10 |
| Decision maker | `decision_maker` name is known | +5 |
| Retirement likelihood (high) | `retirement_score` >= 60 | +10 |
| Retirement likelihood (medium) | `retirement_score` >= 40 (but < 60) | +5 |

**Maximum theoretical score:** 110 (capped to 100)

### How It's Used
- Displayed in the pipeline UI as the primary lead quality indicator
- Filterable via `min_score` query parameter on `GET /pipeline/`
- Included in pipeline stats (`avg_score`)
- Written into Contact notes when a lead is approved

---

## 2. Retirement Likelihood Score (0–100)

**Source:** `backend/app/services/enrichment_service.py` — `EnrichmentService._heuristic_retirement_score()`

Estimates the probability that the business owner is nearing retirement, based on heuristic signals gathered during enrichment (website scraping + optional Tavily web search).

### Scoring Factors

| Signal | Condition | Points |
|---|---|---|
| Year founded (very old) | Business founded >= 35 years ago | +30 |
| Year founded (old) | Business founded >= 25 years ago (but < 35) | +15 |
| Tenure language | Website text contains tenure phrases (e.g., "40 years of experience") | +20 |
| Biographical signals | Bio text detected on website (e.g., age/career references) | +15 |
| Stale copyright | Website copyright year >= 3 years behind current year | +10 |
| No social media | Website has no social media links | +5 |
| Outdated design | Visual indicators of an outdated website | +5 |
| Family business (original generation) | Family-owned, no succession completed | +10 |
| Single owner, no succession | Solo owner with no visible succession plan | +10 |
| High-retirement industry | Business category matches known trade/service industries | +5 |
| Web search signals | Tavily search found retirement/succession mentions | +15 |
| Succession already completed | Son/daughter took over (younger owner likely) | **-25** |

**Score is clamped to 0–100.**

### Labels

| Score Range | Label |
|---|---|
| >= 75 | `high` |
| >= 40 | `medium` |
| >= 1 | `low` |
| 0 | `unknown` |

### High-Retirement Industries

The following business categories receive a +5 bonus:

> plumber, plumbing, electrician, electrical, hvac, heating, auto_repair, mechanic, roofing, roofer, painting, painter, locksmith, landscaping, landscaper, carpet_cleaning, dry_cleaner, laundromat, barber, hair_salon, florist, bakery, deli, hardware_store, print_shop, tailor, upholstery, welding, general_contractor, masonry, concrete, fencing, pest_control, janitorial, cleaning_service, moving_company, towing

### How It's Used
- Stored on the `Lead` model as `retirement_score` and `retirement_label`
- Filterable via `min_retirement` and `retirement_label` query parameters on `GET /pipeline/`
- Pipeline stats track `with_high_retirement` (leads with score >= 60)
- Feeds into Lead Quality Score as a bonus (+5 or +10 depending on value)

---

## 3. Email Confidence Score (0.0–1.0)

**Source:** `backend/app/services/confidence_scorer.py` — `ConfidenceScorer.score()`

Evaluates the quality of a generated outreach email to decide whether it can be auto-sent or needs human review. Purely heuristic — no additional AI calls.

### Dimensions & Weights

| Dimension | Weight | What It Measures |
|---|---|---|
| `personalization_depth` | 30% | Mentions of recipient name, company, website issues, custom fields |
| `spam_safety` | 20% | Inverse of spam score (0–100 from spam checker); lower spam = higher safety |
| `content_coherence` | 20% | Word count in range, greeting present, CTA present, no leftover placeholders |
| `relevance_signal` | 20% | Severity of website issues found (critical > important > minor > none) |
| `historical_match` | 10% | Body length similarity to historically winning emails in the workspace |

**Final score** = weighted average of all five dimensions.

### Personalization Depth (0.0–1.0)
Counts how many available data points (recipient name, company, website observations, custom fields) actually appear in the email body. Base score of 0.2 for generating an email at all, plus proportional credit for each match. Returns 0.5 if no personalization data was available.

### Spam Safety (0.0–1.0)
Computed as `1.0 - (spam_score / 100)`. Falls back to 0.7 (neutral) if the spam checker is unavailable.

### Content Coherence (0.0–1.0)
Four sub-checks, each worth up to 1.0 point, averaged over 4:
- **Word count**: 1.0 if 80–350 words, 0.7 if 50–500, 0.3 otherwise
- **Greeting**: 1.0 if starts with greeting, 0.7 if greeting in first 100 chars
- **CTA**: 1.0 if a call-to-action phrase is found, 0.3 otherwise
- **Placeholders**: 1.0 if no leftover `{{...}}` / `[INSERT...]` / `[PLACEHOLDER]` tokens

Subject line with leftover placeholders or fewer than 6 characters deducts 0.3.

### Relevance Signal (0.0–1.0)
Based on website analysis issue severity:

| Condition | Score |
|---|---|
| Critical issues found | 0.95 |
| Important issues found | 0.85 |
| Minor issues found | 0.60 |
| Analysis ran, nothing specific | 0.40 |
| No analysis available | 0.30 |

### Historical Match (0.0–1.0)
Compares the generated email's word count to the average word count of "winner" emails in the workspace:

| Body-length Ratio (vs. winner avg) | Score |
|---|---|
| 0.7–1.3x | 0.80 |
| 0.5–1.5x | 0.60 |
| Outside range or insufficient data | 0.50 |

### Recommendations

| Confidence | Action |
|---|---|
| >= 0.8 | `auto_send` — email is sent without review |
| >= 0.5 | `review` — queued for human approval |
| < 0.5 | `regenerate` — email is discarded and regenerated |

---

## 4. Email Engagement Score (point-based)

**Source:** `backend/app/services/email_scoring.py` — `score_email()`

Scores previously **sent** emails based on recipient engagement signals. Used to identify winning and losing email patterns for future optimization.

### Scoring Weights

| Signal | Condition | Points |
|---|---|---|
| Opened | `opened_at` is set | +2 |
| Clicked | `clicked_at` is set | +5 |
| Reply (positive sentiment) | Reply exists with `sentiment = 'positive'` | +15 |
| Reply (neutral sentiment) | Reply exists with `sentiment = 'neutral'` | +8 |
| Reply (negative sentiment) | Reply exists with `sentiment = 'negative'` | +3 |
| Reply (unknown sentiment) | Reply exists but no sentiment classified | +8 |

**Maximum possible score per email:** 22 (opened + clicked + positive reply)

### Winner/Loser Classification

**Source:** `backend/app/services/email_scoring.py` — `get_winners_and_losers()`

Emails are sorted by score descending, then split into percentile-based tiers (default: 25th percentile):

| Tier | Definition |
|---|---|
| `winner` | Top 25% by score |
| `loser` | Bottom 25% by score |
| `middle` | Everything in between |

Classification is per-workspace — tiers adapt to each workspace's own distribution.

### How It's Used
- Winners inform the **Historical Match** dimension of the Email Confidence Score
- Helps identify which email styles, lengths, and approaches perform best
- Available via the email scoring API for workspace analytics

---

## 5. Pipeline Filtering & Sorting

**Source:** `backend/app/routes/pipeline.py` — `GET /pipeline/`

The pipeline API exposes all scoring data for filtering and sorting leads.

### Available Filters

| Parameter | Type | Description |
|---|---|---|
| `status` | string | Filter by lead status (comma-separated for multiple) |
| `source` | string | Filter by lead source |
| `min_score` | int | Minimum lead quality score |
| `min_retirement` | int | Minimum retirement likelihood score |
| `retirement_label` | string | Filter by retirement label (`high`, `medium`, `low`, `unknown`) |

### Sorting

| Parameter | Default | Options |
|---|---|---|
| `sort` | `created_at` | Any `Lead` model column (e.g., `score`, `retirement_score`, `created_at`) |
| `order` | `desc` | `asc` or `desc` |

### Pipeline Stats (`GET /pipeline/stats`)

| Metric | Description |
|---|---|
| `total` | Total leads in workspace |
| `by_status` | Count per status |
| `avg_score` | Average lead quality score |
| `with_email` | Leads that have at least one discovered email |
| `with_employee_count` | Leads with employee count populated |
| `with_high_retirement` | Leads with `retirement_score` >= 60 |

---

## Score Lifecycle

```
Lead Created (score = null)
    │
    ▼
Enrichment runs
    ├── Website scraped → retirement signals extracted
    ├── Tavily web search (optional) → retirement signals
    ├── _heuristic_retirement_score() → retirement_score + retirement_label
    └── calculate_score() → lead quality score + breakdown
    │
    ▼
Pipeline UI displays scores, allows filtering/sorting
    │
    ▼
Lead approved → Contact created → added to Campaign
    │
    ▼
Email generated
    ├── ConfidenceScorer.score() → auto_send / review / regenerate
    │
    ▼
Email sent → engagement tracked
    └── score_email() → engagement score → winner/loser tier
                              │
                              └── Feeds back into ConfidenceScorer.historical_match
```
