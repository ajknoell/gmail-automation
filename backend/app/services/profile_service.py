"""
Profile Service — manages business profiles and computes relevance
scores between signals and the user's service offerings.
"""
import logging

logger = logging.getLogger(__name__)


class ProfileService:
    """Manages BusinessProfile and computes signal relevance."""

    @classmethod
    def get_profile(cls, workspace_id):
        """Get or create empty business profile for workspace."""
        from app import db
        from app.models.business_profile import BusinessProfile

        profile = BusinessProfile.query.filter_by(workspace_id=workspace_id).first()
        if not profile:
            profile = BusinessProfile(workspace_id=workspace_id)
            db.session.add(profile)
            db.session.commit()
        return profile

    @classmethod
    def score_relevance(cls, signal, workspace_id):
        """
        Score how relevant a signal is to the business profile.
        Returns float 0.0-1.0. Heuristic, no AI calls.
        """
        from app.models.business_profile import BusinessProfile

        profile = BusinessProfile.query.filter_by(workspace_id=workspace_id).first()
        if not profile:
            return 0.5  # No profile configured, neutral score

        score = 0.0
        checks = 0

        # Get profile data
        keywords = profile.get_keywords()
        capabilities = profile.get_capabilities()
        target_market = profile.get_target_market()

        # Build keyword set from all profile data
        profile_keywords = set()
        for kw in keywords:
            if isinstance(kw, str):
                profile_keywords.add(kw.lower())

        for cap in capabilities:
            if isinstance(cap, dict):
                for kw in cap.get('keywords', []):
                    if isinstance(kw, str):
                        profile_keywords.add(kw.lower())
                name = cap.get('name', '')
                if name:
                    profile_keywords.update(name.lower().split())

        # Add industry keywords
        target_industries = target_market.get('industries', [])
        for ind in target_industries:
            if isinstance(ind, str):
                profile_keywords.add(ind.lower())

        if not profile_keywords:
            return 0.5  # No keywords to match against

        # Build signal text to match against
        signal_text = ' '.join(filter(None, [
            signal.title or '',
            signal.summary or '',
            signal.signal_type or '',
        ])).lower()

        # Also include contact's business category if available
        if signal.contact_id:
            contact = signal.contact
            if contact:
                if contact.business_category:
                    signal_text += ' ' + contact.business_category.lower()
                if contact.company:
                    signal_text += ' ' + contact.company.lower()

        # 1. Keyword matching (0-1)
        if profile_keywords:
            checks += 1
            matches = sum(1 for kw in profile_keywords if kw in signal_text)
            keyword_score = min(1.0, matches / max(1, len(profile_keywords) * 0.3))
            score += keyword_score

        # 2. Industry matching (0-1)
        if target_industries and signal.contact_id:
            checks += 1
            contact = signal.contact
            if contact and contact.business_category:
                cat = contact.business_category.lower()
                industry_match = any(ind.lower() in cat for ind in target_industries)
                score += 1.0 if industry_match else 0.2

        # 3. Signal type relevance bonus
        checks += 1
        type_scores = {
            'funding_round': 0.8,
            'expansion': 0.7,
            'leadership_change': 0.75,
            'hiring': 0.7,
            'ssl_expiry': 0.6,
            'downtime': 0.7,
            'copyright_outdated': 0.5,
            'content_change': 0.3,
            'product_launch': 0.6,
        }
        score += type_scores.get(signal.signal_type, 0.5)

        if checks == 0:
            return 0.5

        return min(1.0, max(0.0, round(score / checks, 3)))
