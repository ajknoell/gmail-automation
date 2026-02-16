"""
Email Insights Service

Core analysis engine that:
1. Scores all sent emails in a workspace
2. Identifies winners (top 25%) and losers (bottom 25%)
3. Sends representative samples to Claude for comparative analysis
4. Extracts structured, actionable insights
5. Caches insights in WorkspaceSettings for use in future email generation
"""

import json
import random
from datetime import datetime

from app.models.email_log import EmailLog
from app.models.reply_message import ReplyMessage
from app.models.settings import WorkspaceSettings
from app.services.email_scoring import (
    score_emails_for_workspace,
    get_winners_and_losers,
)
from app.services.claude_service import ClaudeService


MIN_EMAILS_FOR_ANALYSIS = 20
MAX_SAMPLES_PER_TIER = 8


class EmailInsightsService:
    """Orchestrates email performance analysis using Claude."""

    def __init__(self, api_key):
        self.claude = ClaudeService(api_key)

    # ── Public API ────────────────────────────────────────────────────

    def analyze_performance(self, workspace_id):
        """
        Run the full analysis pipeline.

        Returns:
            {
                "status": "success" | "insufficient_data",
                "insights": { ... } | None,
                "metadata": { ... } | None,
                "count": int  (only if insufficient_data)
            }
        """
        scored = score_emails_for_workspace(workspace_id)

        if len(scored) < MIN_EMAILS_FOR_ANALYSIS:
            return {
                'status': 'insufficient_data',
                'count': len(scored),
                'minimum': MIN_EMAILS_FOR_ANALYSIS,
            }

        winners, losers = get_winners_and_losers(scored)

        # Sample if we have too many
        winner_sample = _sample(winners, MAX_SAMPLES_PER_TIER)
        loser_sample = _sample(losers, MAX_SAMPLES_PER_TIER)

        # Build & send analysis prompt to Claude
        prompt = self._build_analysis_prompt(winner_sample, loser_sample, len(scored))
        insights = self._run_analysis(prompt)

        if not insights:
            return {
                'status': 'error',
                'message': 'Failed to parse Claude analysis response',
            }

        # Determine confidence level
        n = len(scored)
        if n >= 100:
            insights['confidence'] = 'high'
        elif n >= 50:
            insights['confidence'] = 'medium'
        else:
            insights['confidence'] = 'low'

        # Compute summary stats
        summary = self._compute_summary(scored)

        # Build metadata
        metadata = {
            'analyzed_at': datetime.utcnow().isoformat(),
            'email_count': len(scored),
            'winner_count': len(winners),
            'loser_count': len(losers),
            'avg_score': summary['avg_score'],
            'confidence': insights['confidence'],
        }

        # Persist to workspace settings
        from app import db
        WorkspaceSettings.set(workspace_id, 'learned_insights', json.dumps(insights))
        WorkspaceSettings.set(workspace_id, 'insights_metadata', json.dumps(metadata))
        db.session.commit()

        return {
            'status': 'success',
            'insights': insights,
            'metadata': metadata,
            'summary': summary,
        }

    def get_insights(self, workspace_id):
        """Return cached insights, or None."""
        raw = WorkspaceSettings.get(workspace_id, 'learned_insights')
        if raw:
            try:
                return json.loads(raw)
            except Exception:
                pass
        return None

    def get_insights_metadata(self, workspace_id):
        """Return analysis metadata, or None."""
        raw = WorkspaceSettings.get(workspace_id, 'insights_metadata')
        if raw:
            try:
                return json.loads(raw)
            except Exception:
                pass
        return None

    def get_email_scores(self, workspace_id):
        """Return per-email scores for the dashboard table."""
        scored = score_emails_for_workspace(workspace_id)
        get_winners_and_losers(scored)  # tags tiers in-place
        # Strip full body for the API response — keep it lightweight
        for e in scored:
            e['body_preview'] = (e.get('body') or '')[:150]
            e.pop('body', None)
        return scored

    def get_performance_summary(self, workspace_id):
        """Compute live aggregate stats (no Claude call needed)."""
        scored = score_emails_for_workspace(workspace_id)
        return self._compute_summary(scored)

    # ── Internal ──────────────────────────────────────────────────────

    def _compute_summary(self, scored):
        """Compute aggregate performance metrics from scored emails."""
        if not scored:
            return {
                'total_sent': 0,
                'open_rate': 0,
                'click_rate': 0,
                'reply_rate': 0,
                'positive_reply_rate': 0,
                'avg_score': 0,
            }

        n = len(scored)
        opened = sum(1 for e in scored if e['breakdown'].get('opened'))
        clicked = sum(1 for e in scored if e['breakdown'].get('clicked'))
        replied = sum(1 for e in scored if e['breakdown'].get('replied'))
        positive = sum(1 for e in scored if e['breakdown'].get('sentiment') == 'positive')

        scores = [e['score'] for e in scored]

        return {
            'total_sent': n,
            'open_rate': round(opened / n * 100, 1) if n else 0,
            'click_rate': round(clicked / n * 100, 1) if n else 0,
            'reply_rate': round(replied / n * 100, 1) if n else 0,
            'positive_reply_rate': round(positive / n * 100, 1) if n else 0,
            'avg_score': round(sum(scores) / n, 1) if n else 0,
        }

    def _build_analysis_prompt(self, winners, losers, total_count):
        """Build the Claude comparison prompt."""

        def _format_email(e, idx):
            breakdown_parts = []
            if e['breakdown'].get('opened'):
                breakdown_parts.append(f"Opened ({e['open_count']}x)")
            if e['breakdown'].get('clicked'):
                breakdown_parts.append(f"Clicked ({e['click_count']}x)")
            if e['breakdown'].get('replied'):
                sentiment = e['breakdown'].get('sentiment', 'unknown')
                breakdown_parts.append(f"Reply received ({sentiment})")
            engagement = ', '.join(breakdown_parts) if breakdown_parts else 'No engagement'

            return f"""--- Email {idx + 1} (Score: {e['score']}) ---
Engagement: {engagement}
Subject: {e['subject']}
Body:
{e['body'] or '(no body)'}
"""

        winner_block = '\n'.join(_format_email(e, i) for i, e in enumerate(winners))
        loser_block = '\n'.join(_format_email(e, i) for i, e in enumerate(losers))

        return f"""You are an expert cold email analyst. I'm going to show you two groups of outreach emails from the same sender:

- **WINNERS**: Emails that got replies, clicks, and/or opens (top performers)
- **LOSERS**: Emails that got zero or minimal engagement (worst performers)

Your job: Compare the two groups and identify the specific patterns that differentiate them. What makes the winners work? What makes the losers fail?

This analysis is based on {total_count} total sent emails.

═══════════════════════════════════════
TOP PERFORMING EMAILS (WINNERS)
═══════════════════════════════════════
{winner_block}

═══════════════════════════════════════
WORST PERFORMING EMAILS (LOSERS)
═══════════════════════════════════════
{loser_block}

═══════════════════════════════════════

Analyze the patterns and return ONLY a valid JSON object with these exact keys. Each value should be 1-3 concise, actionable sentences:

{{
  "subject_line_patterns": "What works in subject lines vs what doesn't. Be specific about length, style, personalization.",
  "opening_patterns": "How winning emails open vs losing emails. First sentence patterns.",
  "personalization_depth": "How much and what kind of personalization correlates with engagement.",
  "length_insights": "Optimal email length observations. Word count patterns.",
  "cta_patterns": "What calls-to-action drive responses vs which ones fall flat.",
  "tone_insights": "Tone and voice patterns that correlate with engagement.",
  "avoid_patterns": "Specific patterns, phrases, or approaches that consistently underperform.",
  "top_recommendation": "The single most impactful change to make right now based on this data."
}}

Return ONLY the JSON object, no other text."""

    def _run_analysis(self, prompt):
        """Send analysis prompt to Claude and parse JSON response."""
        import re

        try:
            message = self.claude.client.messages.create(
                model='claude-sonnet-4-5-20250929',
                max_tokens=2000,
                messages=[{'role': 'user', 'content': prompt}],
            )

            response_text = message.content[0].text.strip()

            # Try to extract JSON from the response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())

            # Try the full response as JSON
            return json.loads(response_text)

        except Exception as e:
            print(f'Email insights analysis error: {e}')
            return None


def _sample(items, max_count):
    """Return up to max_count items, randomly sampled if list is larger."""
    if len(items) <= max_count:
        return items
    return random.sample(items, max_count)
