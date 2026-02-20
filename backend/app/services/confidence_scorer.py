"""
Confidence Scorer — evaluates generated email quality to determine
whether an email can be auto-sent or needs human review.

Scores are 0.0-1.0 across five dimensions, producing a weighted average.
No extra AI calls are made — purely heuristic analysis.
"""
import re
import json
import logging

logger = logging.getLogger(__name__)


class ConfidenceScorer:
    """Scores generated email quality for auto-send decisions."""

    WEIGHTS = {
        'personalization_depth': 0.30,
        'spam_safety': 0.20,
        'content_coherence': 0.20,
        'relevance_signal': 0.20,
        'historical_match': 0.10,
    }

    @classmethod
    def score(cls, subject, body, recipient_data=None, website_analysis=None,
              spam_score=None, workspace_id=None):
        """
        Calculate confidence score 0.0-1.0 with breakdown.

        Args:
            subject: Generated email subject
            body: Generated email body (HTML or plain text)
            recipient_data: Dict with name, company, custom_fields, etc.
            website_analysis: Dict from WebsiteAnalyzer (issues, recommendation)
            spam_score: Pre-computed spam score (0-100), or None to compute
            workspace_id: For historical pattern matching

        Returns:
            {confidence: float, breakdown: dict, recommendation: str}
        """
        if not body:
            return {
                'confidence': 0.0,
                'breakdown': {},
                'recommendation': 'regenerate',
            }

        breakdown = {}
        recipient_data = recipient_data or {}

        # Strip HTML for text analysis
        text_body = re.sub(r'<[^>]+>', ' ', body)
        text_body = re.sub(r'\s+', ' ', text_body).strip()

        # 1. Personalization depth
        breakdown['personalization_depth'] = cls._score_personalization(
            text_body, subject, recipient_data, website_analysis
        )

        # 2. Spam safety
        if spam_score is not None:
            breakdown['spam_safety'] = max(0.0, 1.0 - spam_score / 100.0)
        else:
            try:
                from app.services.spam_checker import check_spam_score
                result = check_spam_score(subject, body)
                breakdown['spam_safety'] = max(0.0, 1.0 - result['score'] / 100.0)
            except Exception:
                breakdown['spam_safety'] = 0.7  # Neutral default

        # 3. Content coherence
        breakdown['content_coherence'] = cls._score_coherence(subject, text_body)

        # 4. Relevance signal
        breakdown['relevance_signal'] = cls._score_relevance(website_analysis)

        # 5. Historical pattern match
        breakdown['historical_match'] = cls._score_historical(text_body, workspace_id)

        # Weighted average
        confidence = sum(
            breakdown[dim] * cls.WEIGHTS[dim]
            for dim in cls.WEIGHTS
        )

        # Determine recommendation
        if confidence >= 0.8:
            recommendation = 'auto_send'
        elif confidence >= 0.5:
            recommendation = 'review'
        else:
            recommendation = 'regenerate'

        return {
            'confidence': round(confidence, 3),
            'breakdown': {k: round(v, 3) for k, v in breakdown.items()},
            'recommendation': recommendation,
        }

    @classmethod
    def _score_personalization(cls, text_body, subject, recipient_data, website_analysis):
        """
        Score how personalized the email is (0-1).
        Checks for mentions of recipient-specific details.
        """
        score = 0.0
        checks = 0
        hits = 0
        body_lower = text_body.lower()

        # Check recipient name
        name = recipient_data.get('name', '')
        if name:
            checks += 1
            # Check first name
            first_name = name.split()[0] if name.split() else ''
            if first_name and first_name.lower() in body_lower:
                hits += 1

        # Check company name
        company = recipient_data.get('company', '')
        if company:
            checks += 1
            if company.lower() in body_lower:
                hits += 1

        # Check for website-specific observations
        if website_analysis:
            checks += 1
            issues = website_analysis.get('issues', [])
            recommendation = website_analysis.get('recommendation', '')
            # If AI made specific observations, the email should reference them
            if issues or recommendation:
                # Check if any issue keyword appears in body
                for issue in issues[:3]:
                    issue_text = issue.get('observation', '') if isinstance(issue, dict) else str(issue)
                    # Check for at least a few key words from the issue
                    issue_words = [w for w in issue_text.lower().split() if len(w) > 4]
                    if any(w in body_lower for w in issue_words[:3]):
                        hits += 1
                        break

        # Check custom fields usage
        custom_fields = recipient_data.get('custom_fields', {})
        if isinstance(custom_fields, str):
            try:
                custom_fields = json.loads(custom_fields)
            except Exception:
                custom_fields = {}

        for key, value in custom_fields.items():
            if value and isinstance(value, str) and len(value) > 2:
                checks += 1
                if value.lower() in body_lower:
                    hits += 1
                if checks >= 6:  # Cap check count
                    break

        if checks == 0:
            return 0.5  # No data to personalize against

        return min(1.0, hits / max(checks, 1) + 0.2)  # Base 0.2 for generating at all

    @classmethod
    def _score_coherence(cls, subject, text_body):
        """
        Score content coherence (0-1).
        Checks: length, greeting, CTA, no leftover placeholders.
        """
        score = 0.0
        checks = 4

        # 1. Word count in optimal range (100-300 words)
        word_count = len(text_body.split())
        if 80 <= word_count <= 350:
            score += 1.0
        elif 50 <= word_count <= 500:
            score += 0.7
        elif word_count > 0:
            score += 0.3

        # 2. Has greeting pattern
        body_lower = text_body.lower()
        greeting_patterns = ['hi ', 'hello ', 'hey ', 'dear ', 'good morning', 'good afternoon']
        if any(body_lower.startswith(g) or body_lower.startswith('\n' + g) for g in greeting_patterns):
            score += 1.0
        elif any(g in body_lower[:100] for g in greeting_patterns):
            score += 0.7

        # 3. Has CTA (call to action)
        cta_patterns = [
            'would you be open', 'let me know', 'interested in',
            'schedule a call', 'quick chat', 'happy to discuss',
            'would love to', 'can we', 'available for', 'thoughts?',
            'what do you think', 'grab a coffee', 'minutes to chat',
        ]
        if any(p in body_lower for p in cta_patterns):
            score += 1.0
        else:
            score += 0.3

        # 4. No leftover placeholders
        placeholder_patterns = [
            r'\{\{.*?\}\}',           # {{variable}}
            r'\[.*?PLACEHOLDER.*?\]', # [PLACEHOLDER]
            r'\[YOUR\s',              # [YOUR NAME]
            r'\[INSERT\s',            # [INSERT HERE]
            r'\[COMPANY\]',
            r'\[NAME\]',
        ]
        has_placeholder = any(
            re.search(p, text_body, re.IGNORECASE)
            for p in placeholder_patterns
        )
        if not has_placeholder:
            score += 1.0

        # Subject check
        if subject and len(subject) > 5 and not re.search(r'\{\{|\[INSERT|\[PLACEHOLDER', subject):
            pass  # Good subject
        else:
            score -= 0.3

        return max(0.0, min(1.0, score / checks))

    @classmethod
    def _score_relevance(cls, website_analysis):
        """
        Score relevance of website analysis (0-1).
        Higher if real issues were found.
        """
        if not website_analysis:
            return 0.3  # No analysis available

        issues = website_analysis.get('issues', [])
        if not issues:
            return 0.4  # Analysis ran but found nothing specific

        # Check severity of issues
        severities = []
        for issue in issues:
            if isinstance(issue, dict):
                severities.append(issue.get('severity', 'info'))
            else:
                severities.append('info')

        if 'critical' in severities:
            return 0.95
        elif 'important' in severities:
            return 0.85
        elif 'minor' in severities:
            return 0.6
        else:
            return 0.5

    @classmethod
    def _score_historical(cls, text_body, workspace_id):
        """
        Score how well this email matches historically successful patterns (0-1).
        Uses email_scoring to find winners and compare patterns.
        """
        if not workspace_id:
            return 0.5  # No workspace, neutral score

        try:
            from app.services.email_scoring import score_emails_for_workspace, get_winners_and_losers

            scored = score_emails_for_workspace(workspace_id)
            if not scored or len(scored) < 5:
                return 0.5  # Not enough historical data

            winners, losers = get_winners_and_losers(scored)
            if not winners:
                return 0.5

            # Compare body length to winners
            body_len = len(text_body.split())
            winner_lengths = [
                len((w.get('body') or '').split())
                for w in winners
                if w.get('body')
            ]
            if winner_lengths:
                avg_winner_len = sum(winner_lengths) / len(winner_lengths)
                # Score based on how close we are to winner average length
                if avg_winner_len > 0:
                    ratio = body_len / avg_winner_len
                    if 0.7 <= ratio <= 1.3:
                        return 0.8
                    elif 0.5 <= ratio <= 1.5:
                        return 0.6

            return 0.5

        except Exception:
            return 0.5  # On any error, return neutral
