"""
Website Analysis Insights Service

Learning engine that improves website analysis over time by:
1. Joining website analysis logs with email engagement data
2. Splitting into winners (analyses whose emails got replies) vs losers
3. Sending representative samples to Claude for comparative analysis
4. Extracting structured patterns about what makes effective website observations
5. Caching insights in WorkspaceSettings for use in future website analyses
"""

import json
import random
from datetime import datetime

from app.models.website_analysis_log import WebsiteAnalysisLog
from app.models.email_log import EmailLog
from app.models.reply_message import ReplyMessage
from app.models.campaign import Campaign
from app.models.settings import WorkspaceSettings
from app.services.claude_service import ClaudeService


MIN_ANALYSES_FOR_LEARNING = 10
MAX_SAMPLES_PER_TIER = 6


class WebsiteInsightsService:
    """Analyzes which website observations drive email engagement."""

    def __init__(self, api_key):
        self.claude = ClaudeService(api_key)

    # -- Public API -----------------------------------------------------------

    def analyze_performance(self, workspace_id):
        """
        Run the full analysis pipeline.

        Returns:
            {
                "status": "success" | "insufficient_data",
                "insights": { ... } | None,
                "metadata": { ... } | None,
            }
        """
        scored, campaign_contexts = self._score_analyses(workspace_id)

        if len(scored) < MIN_ANALYSES_FOR_LEARNING:
            return {
                'status': 'insufficient_data',
                'count': len(scored),
                'minimum': MIN_ANALYSES_FOR_LEARNING,
            }

        winners, losers = self._split_winners_losers(scored)

        if not winners or not losers:
            return {
                'status': 'insufficient_data',
                'message': 'Need both high and low engagement analyses to compare',
                'count': len(scored),
                'minimum': MIN_ANALYSES_FOR_LEARNING,
            }

        winner_sample = _sample(winners, MAX_SAMPLES_PER_TIER)
        loser_sample = _sample(losers, MAX_SAMPLES_PER_TIER)

        prompt = self._build_analysis_prompt(
            winner_sample, loser_sample, len(scored), campaign_contexts
        )
        insights = self._run_analysis(prompt)

        if not insights:
            return {
                'status': 'error',
                'message': 'Failed to parse Claude analysis response',
            }

        # Confidence based on sample size
        n = len(scored)
        if n >= 50:
            insights['confidence'] = 'high'
        elif n >= 25:
            insights['confidence'] = 'medium'
        else:
            insights['confidence'] = 'low'

        metadata = {
            'analyzed_at': datetime.utcnow().isoformat(),
            'analysis_count': n,
            'winner_count': len(winners),
            'loser_count': len(losers),
            'confidence': insights['confidence'],
        }

        # Persist to workspace settings
        from app import db
        WorkspaceSettings.set(workspace_id, 'learned_website_insights', json.dumps(insights))
        WorkspaceSettings.set(workspace_id, 'website_insights_metadata', json.dumps(metadata))
        db.session.commit()

        return {
            'status': 'success',
            'insights': insights,
            'metadata': metadata,
        }

    def get_insights(self, workspace_id):
        """Return cached website analysis insights, or None."""
        raw = WorkspaceSettings.get(workspace_id, 'learned_website_insights')
        if raw:
            try:
                return json.loads(raw)
            except Exception:
                pass
        return None

    def get_metadata(self, workspace_id):
        """Return analysis metadata, or None."""
        raw = WorkspaceSettings.get(workspace_id, 'website_insights_metadata')
        if raw:
            try:
                return json.loads(raw)
            except Exception:
                pass
        return None

    # -- Internal -------------------------------------------------------------

    def _score_analyses(self, workspace_id):
        """
        Join website analysis logs with email engagement data.

        Returns a list of dicts sorted by engagement score descending.
        """
        analyses = (
            WebsiteAnalysisLog.query
            .filter_by(workspace_id=workspace_id)
            .filter(WebsiteAnalysisLog.email_log_id.isnot(None))
            .all()
        )

        if not analyses:
            return [], set()

        # Batch-load email logs
        log_ids = [a.email_log_id for a in analyses if a.email_log_id]
        email_logs = {
            el.id: el
            for el in EmailLog.query.filter(EmailLog.id.in_(log_ids)).all()
        }

        # Batch-load reply messages
        replies = ReplyMessage.query.filter(
            ReplyMessage.email_log_id.in_(log_ids)
        ).all()
        replies_by_log = {}
        for r in replies:
            replies_by_log.setdefault(r.email_log_id, []).append(r)

        # Batch-load campaigns for business context
        campaign_ids = {el.campaign_id for el in email_logs.values() if el.campaign_id}
        campaigns = {}
        if campaign_ids:
            campaigns = {
                c.id: c
                for c in Campaign.query.filter(Campaign.id.in_(campaign_ids)).all()
            }

        scored = []
        campaign_contexts = set()
        for analysis in analyses:
            el = email_logs.get(analysis.email_log_id)
            if not el:
                continue

            # Collect campaign context for business understanding
            if el.campaign_id and el.campaign_id in campaigns:
                camp = campaigns[el.campaign_id]
                if camp.campaign_context:
                    campaign_contexts.add(camp.campaign_context.strip())
                if camp.ai_prompt:
                    campaign_contexts.add(camp.ai_prompt.strip())

            score = 0.0
            engagement = []

            if el.opened_at is not None:
                score += 2
                engagement.append(f'Opened ({el.open_count or 1}x)')

            if el.clicked_at is not None:
                score += 5
                engagement.append(f'Clicked ({el.click_count or 1}x)')

            log_replies = replies_by_log.get(el.id, [])
            if log_replies:
                sentiments = [r.sentiment for r in log_replies if r.sentiment]
                if 'positive' in sentiments:
                    score += 15
                    engagement.append('Positive reply')
                elif 'neutral' in sentiments:
                    score += 8
                    engagement.append('Neutral reply')
                elif 'negative' in sentiments:
                    score += 3
                    engagement.append('Negative reply')
                else:
                    score += 8
                    engagement.append('Reply (unclassified)')
            elif el.replied_at is not None:
                score += 8
                engagement.append('Reply (unclassified)')

            scored.append({
                'analysis_id': analysis.id,
                'url': analysis.url,
                'company': analysis.company,
                'analysis_result': analysis.analysis_result,
                'raw_text_preview': analysis.raw_text_preview,
                'score': score,
                'engagement': ', '.join(engagement) if engagement else 'No engagement',
            })

        scored.sort(key=lambda x: x['score'], reverse=True)
        return scored, campaign_contexts

    def _split_winners_losers(self, scored, percentile=0.30):
        """Split into top-performing and bottom-performing analyses."""
        if not scored:
            return [], []

        n = len(scored)
        cutoff = max(1, int(n * percentile))

        winners = [s for s in scored[:cutoff] if s['score'] > 0]
        losers = scored[-cutoff:]

        return winners, losers

    def _build_analysis_prompt(self, winners, losers, total_count, campaign_contexts=None):
        """Build the Claude comparison prompt for website analysis patterns."""

        def _fmt(entry, idx):
            return f"""--- Analysis {idx + 1} (Engagement score: {entry['score']}) ---
URL: {entry['url']}
Company: {entry['company'] or 'Unknown'}
Engagement: {entry['engagement']}
Website observations used in email:
{entry['analysis_result']}
"""

        winner_block = '\n'.join(_fmt(e, i) for i, e in enumerate(winners))
        loser_block = '\n'.join(_fmt(e, i) for i, e in enumerate(losers))

        # Build business context section
        biz_context = ''
        if campaign_contexts:
            ctx_list = '\n'.join(f'- {c}' for c in campaign_contexts)
            biz_context = f"""
===================================================
SENDER'S BUSINESS CONTEXT
===================================================
These emails are sent by a business that describes itself / its service as:
{ctx_list}

CRITICAL: The sender's service directly affects WHY certain observations drive engagement.
For example, if the sender offers web design services, then observations about broken or
poorly designed websites resonate because they demonstrate the sender's expertise and the
recipient's need for the sender's service. This does NOT mean "always mention broken
websites" — it means observations that ALIGN WITH WHAT THE SENDER CAN HELP WITH are
more compelling. An observation is effective when it's both accurate AND relevant to what
the sender offers.

"""

        return f"""You are an expert at analyzing cold email outreach effectiveness. I'm going to show you two groups of WEBSITE ANALYSES that were used to personalize outreach emails:

- **WINNERS**: Website observations that were included in emails that got replies/clicks/engagement
- **LOSERS**: Website observations that were included in emails that got zero engagement

Your job: Compare the two groups and identify what makes website observations effective at driving replies. Focus on the QUALITY and RELEVANCE of the observations, not just surface-level patterns.
{biz_context}
This is based on {total_count} total website analyses.

===================================================
TOP PERFORMING WEBSITE OBSERVATIONS (WINNERS)
===================================================
{winner_block}

===================================================
WORST PERFORMING WEBSITE OBSERVATIONS (LOSERS)
===================================================
{loser_block}

===================================================

IMPORTANT ANALYSIS GUIDELINES:
- Consider WHY an observation drove engagement — was it because it was accurate, specific,
  and relevant to the sender's expertise? Or was it generic advice anyone could give?
- Distinguish between observations that work because they match the sender's service offering
  vs observations that would work for any cold email.
- "Broken website = good observation" is WRONG thinking. "Accurately identifying a real problem
  that the sender can specifically help fix = good observation" is RIGHT.
- The best observations demonstrate the sender's expertise by noticing things a non-expert
  would miss.

Analyze the patterns and return ONLY a valid JSON object with these exact keys. Each value should be 1-3 concise, actionable sentences:

{{
  "observation_types_that_work": "What kinds of observations drive engagement? Focus on the qualities (accuracy, specificity, relevance to sender's expertise) rather than surface topics.",
  "observation_types_to_avoid": "What kinds of observations fall flat? Consider whether they failed because they were generic, inaccurate, or irrelevant to what the sender actually offers.",
  "framing_patterns": "How should observations be framed? (benefit-led vs problem-led, tone, specificity level)",
  "priority_focus_areas": "What areas of a website should the analyzer focus on? Prioritize areas where the sender can demonstrate real expertise.",
  "personalization_depth": "How much should observations reference the recipient's specific business vs generic advice?",
  "length_and_detail": "How detailed/long should each observation be for maximum impact?",
  "top_recommendation": "The single most impactful change to make to website analysis right now based on this data."
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
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return json.loads(response_text)

        except Exception as e:
            print(f'Website insights analysis error: {e}')
            return None


def _sample(items, max_count):
    """Return up to max_count items, randomly sampled if list is larger."""
    if len(items) <= max_count:
        return items
    return random.sample(items, max_count)
