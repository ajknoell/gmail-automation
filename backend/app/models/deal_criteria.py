"""
Deal Criteria — workspace-level filters that control which scraped
listings are saved. Listings that don't match active criteria are
discarded at scrape time so only relevant deals appear.
"""
from app import db
from datetime import datetime
import json


class DealCriteria(db.Model):
    __tablename__ = 'deal_criteria'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, nullable=False, index=True)

    # Toggle: when False, all listings are saved regardless of criteria
    is_active = db.Column(db.Boolean, default=False)

    # ── Price / Asking ──
    price_min = db.Column(db.Float)
    price_max = db.Column(db.Float)

    # ── Revenue ──
    revenue_min = db.Column(db.Float)
    revenue_max = db.Column(db.Float)

    # ── Cash Flow ──
    cash_flow_min = db.Column(db.Float)
    cash_flow_max = db.Column(db.Float)

    # ── SDE (Seller's Discretionary Earnings) ──
    sde_min = db.Column(db.Float)
    sde_max = db.Column(db.Float)

    # ── EBITDA ──
    ebitda_min = db.Column(db.Float)
    ebitda_max = db.Column(db.Float)

    # ── Net Profit ──
    net_profit_min = db.Column(db.Float)
    net_profit_max = db.Column(db.Float)

    # ── Location ──
    # Comma-separated keywords, e.g. "New Jersey, Bergen County"
    # Listing matches if its location contains ANY of these
    locations = db.Column(db.Text)

    # ── Category / Industry ──
    # Comma-separated, e.g. "Restaurant, Food"
    categories = db.Column(db.Text)

    # ── Keywords ──
    # Comma-separated keywords to match in title or description
    # Listing matches if title/desc contains ANY keyword
    include_keywords = db.Column(db.Text)

    # Keywords that EXCLUDE a listing if found in title/desc
    exclude_keywords = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def listing_matches(self, listing_dict):
        """Check if a raw listing dict passes these criteria.

        A listing matches if it satisfies ALL active numeric range filters.
        For text filters (location, category, keywords), the listing matches
        if ANY of the comma-separated values is found.
        Fields that are None on the listing are treated as passing
        (we don't reject a listing just because it lacks data).

        Returns True if listing should be saved, False if filtered out.
        """
        if not self.is_active:
            return True

        # ── Numeric range checks ──
        range_checks = [
            ('price_numeric', self.price_min, self.price_max),
            ('revenue', self.revenue_min, self.revenue_max),
            ('cash_flow', self.cash_flow_min, self.cash_flow_max),
            ('sde', self.sde_min, self.sde_max),
            ('ebitda', self.ebitda_min, self.ebitda_max),
            ('net_profit', self.net_profit_min, self.net_profit_max),
        ]

        for field, fmin, fmax in range_checks:
            val = listing_dict.get(field)
            # If the criteria has a range set but the listing has no data,
            # skip (don't filter out — many listings omit financials)
            if val is None:
                continue
            if fmin is not None and val < fmin:
                return False
            if fmax is not None and val > fmax:
                return False

        # ── Location filter ──
        if self.locations:
            loc = listing_dict.get('location') or ''
            if loc:
                loc_keywords = [k.strip().lower() for k in self.locations.split(',') if k.strip()]
                if loc_keywords and not any(kw in loc.lower() for kw in loc_keywords):
                    return False

        # ── Category filter ──
        if self.categories:
            cat = listing_dict.get('category') or ''
            if cat:
                cat_keywords = [k.strip().lower() for k in self.categories.split(',') if k.strip()]
                if cat_keywords and not any(kw in cat.lower() for kw in cat_keywords):
                    return False

        # ── Include keywords ──
        if self.include_keywords:
            searchable = f"{listing_dict.get('title', '')} {listing_dict.get('description', '')}".lower()
            inc_keywords = [k.strip().lower() for k in self.include_keywords.split(',') if k.strip()]
            if inc_keywords and not any(kw in searchable for kw in inc_keywords):
                return False

        # ── Exclude keywords ──
        if self.exclude_keywords:
            searchable = f"{listing_dict.get('title', '')} {listing_dict.get('description', '')}".lower()
            exc_keywords = [k.strip().lower() for k in self.exclude_keywords.split(',') if k.strip()]
            if any(kw in searchable for kw in exc_keywords):
                return False

        return True

    def to_dict(self):
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'is_active': self.is_active,
            'price_min': self.price_min,
            'price_max': self.price_max,
            'revenue_min': self.revenue_min,
            'revenue_max': self.revenue_max,
            'cash_flow_min': self.cash_flow_min,
            'cash_flow_max': self.cash_flow_max,
            'sde_min': self.sde_min,
            'sde_max': self.sde_max,
            'ebitda_min': self.ebitda_min,
            'ebitda_max': self.ebitda_max,
            'net_profit_min': self.net_profit_min,
            'net_profit_max': self.net_profit_max,
            'locations': self.locations,
            'categories': self.categories,
            'include_keywords': self.include_keywords,
            'exclude_keywords': self.exclude_keywords,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
