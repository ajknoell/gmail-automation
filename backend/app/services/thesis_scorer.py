"""
Thesis Scorer — scores leads against acquisition thesis criteria.
Primary size proxy is employee count (revenue unavailable for private companies).
Review volume is the secondary revenue signal.
"""
import logging
from datetime import datetime

from app import db
from app.models.lead import Lead
from app.models.acquisition_thesis import AcquisitionThesis

logger = logging.getLogger(__name__)

# Scoring weights (total = 100)
WEIGHT_EMPLOYEE_COUNT = 25
WEIGHT_GEOGRAPHY = 20
WEIGHT_CATEGORY = 20
WEIGHT_YEARS_IN_OPERATION = 15
WEIGHT_REVIEW_VOLUME = 10
WEIGHT_LOCATION_COUNT = 10


class ThesisScorer:
    """Scores leads against acquisition thesis criteria."""

    @staticmethod
    def score_lead(lead: Lead, thesis: AcquisitionThesis) -> dict:
        """Score a single lead against a thesis.

        Returns dict with total score (0-100) and breakdown.
        """
        breakdown = {}
        total = 0

        # 1. Employee count fit (25 pts)
        emp_score = _score_range(
            lead.employee_count,
            thesis.min_employee_count,
            thesis.max_employee_count,
        )
        points = int(emp_score * WEIGHT_EMPLOYEE_COUNT)
        breakdown['employee_count'] = {'score': points, 'max': WEIGHT_EMPLOYEE_COUNT,
                                       'value': lead.employee_count}
        total += points

        # 2. Geography match (20 pts)
        geo_score = _score_geography(lead, thesis)
        points = int(geo_score * WEIGHT_GEOGRAPHY)
        breakdown['geography'] = {'score': points, 'max': WEIGHT_GEOGRAPHY,
                                  'value': lead.address}
        total += points

        # 3. Category match (20 pts)
        cat_score = _score_category(lead, thesis)
        points = int(cat_score * WEIGHT_CATEGORY)
        breakdown['category'] = {'score': points, 'max': WEIGHT_CATEGORY,
                                 'value': lead.business_category}
        total += points

        # 4. Years in operation (15 pts)
        years = lead.years_in_operation
        if years is None and lead.year_founded:
            try:
                years = datetime.utcnow().year - int(lead.year_founded)
            except (ValueError, TypeError):
                years = None
        yrs_score = _score_range(
            years,
            thesis.min_years_in_operation,
            thesis.max_years_in_operation,
        )
        points = int(yrs_score * WEIGHT_YEARS_IN_OPERATION)
        breakdown['years_in_operation'] = {'score': points, 'max': WEIGHT_YEARS_IN_OPERATION,
                                           'value': years}
        total += points

        # 5. Review volume (10 pts) — revenue proxy
        review_vol = lead.total_review_volume or lead.review_count
        rv_score = 0.0
        if review_vol is not None and thesis.min_review_volume:
            if review_vol >= thesis.min_review_volume:
                rv_score = 1.0
            else:
                rv_score = review_vol / thesis.min_review_volume
        elif review_vol is not None:
            # No threshold set — give partial credit for having reviews
            rv_score = min(review_vol / 100, 1.0)
        points = int(rv_score * WEIGHT_REVIEW_VOLUME)
        breakdown['review_volume'] = {'score': points, 'max': WEIGHT_REVIEW_VOLUME,
                                      'value': review_vol}
        total += points

        # 6. Location count (10 pts)
        loc_score = _score_range(
            lead.location_count,
            thesis.min_location_count,
            thesis.max_location_count,
        )
        points = int(loc_score * WEIGHT_LOCATION_COUNT)
        breakdown['location_count'] = {'score': points, 'max': WEIGHT_LOCATION_COUNT,
                                       'value': lead.location_count}
        total += points

        return {
            'score': total,
            'breakdown': breakdown,
        }

    @staticmethod
    def score_batch(leads: list[Lead], thesis: AcquisitionThesis) -> list[dict]:
        """Score a batch of leads efficiently.

        Returns list of dicts with lead_id, score, and breakdown.
        """
        results = []
        for lead in leads:
            result = ThesisScorer.score_lead(lead, thesis)
            results.append({
                'lead_id': lead.id,
                **result,
            })
        return results

    @staticmethod
    def rank_leads(
        workspace_id: int,
        thesis_id: int,
        limit: int = 50,
        min_score: int = 0,
    ) -> list[dict]:
        """Return top leads ranked by thesis fit score.

        Fetches enriched leads, scores them against the thesis,
        and returns ranked results with full lead data.
        """
        thesis = AcquisitionThesis.query.get(thesis_id)
        if not thesis:
            return []

        # Get enriched leads (status beyond 'new')
        leads = Lead.query.filter(
            Lead.workspace_id == workspace_id,
            Lead.status.notin_(['new', 'rejected']),
        ).all()

        scored = []
        for lead in leads:
            result = ThesisScorer.score_lead(lead, thesis)
            if result['score'] >= min_score:
                scored.append({
                    'lead': lead.to_dict(),
                    'thesis_fit_score': result['score'],
                    'score_breakdown': result['breakdown'],
                })

                # Persist the score on the lead for sorting/filtering elsewhere
                if lead.thesis_fit_score != result['score']:
                    lead.thesis_fit_score = result['score']

        # Sort by score descending
        scored.sort(key=lambda x: x['thesis_fit_score'], reverse=True)

        # Commit any score updates
        try:
            db.session.commit()
        except Exception as e:
            logger.warning(f"Failed to persist thesis fit scores: {e}")
            db.session.rollback()

        return scored[:limit]


def _score_range(value: int | None, min_val: int | None, max_val: int | None) -> float:
    """Score a numeric value against a min/max range.

    Returns 1.0 for perfect fit, 0.5 for partial, 0.0 for missing data.
    """
    if value is None:
        return 0.0

    # No criteria set — give partial credit for having data
    if min_val is None and max_val is None:
        return 0.5

    in_range = True
    if min_val is not None and value < min_val:
        in_range = False
    if max_val is not None and value > max_val:
        in_range = False

    if in_range:
        return 1.0

    # Partial credit: how close are they?
    if min_val is not None and value < min_val:
        if min_val == 0:
            return 0.0
        return max(0.0, value / min_val * 0.5)

    if max_val is not None and value > max_val:
        if max_val == 0:
            return 0.0
        return max(0.0, max_val / value * 0.5)

    return 0.0


def _score_geography(lead: Lead, thesis: AcquisitionThesis) -> float:
    """Score lead geography against thesis target geographies.

    Returns 1.0 for match, 0.0 for no data or no match.
    """
    targets = thesis.get_target_geographies()
    if not targets:
        return 0.5  # No geo criteria — partial credit

    address = (lead.address or '').lower()
    if not address:
        return 0.0

    for geo in targets:
        if geo.lower() in address:
            return 1.0

    return 0.0


def _score_category(lead: Lead, thesis: AcquisitionThesis) -> float:
    """Score lead category against thesis target/exclude categories.

    Returns 1.0 for match, 0.0 for excluded or no match.
    """
    category = (lead.business_category or '').lower()
    if not category:
        return 0.0

    # Check exclusions first
    excludes = thesis.get_exclude_categories()
    for exc in excludes:
        if exc.lower() in category:
            return 0.0

    targets = thesis.get_target_categories()
    if not targets:
        return 0.5  # No category criteria — partial credit

    for cat in targets:
        if cat.lower() in category or category in cat.lower():
            return 1.0

    # Check vertical as fallback
    if thesis.vertical and thesis.vertical.lower() in category:
        return 0.8

    return 0.0
