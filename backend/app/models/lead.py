import json
from app import db
from datetime import datetime


LEAD_STATUSES = ['new', 'enriching', 'enriched', 'qualified', 'approved', 'in_campaign', 'rejected']

LEAD_STATUS_LABELS = {
    'new': 'New',
    'enriching': 'Enriching...',
    'enriched': 'Enriched',
    'qualified': 'Qualified',
    'approved': 'Approved',
    'in_campaign': 'In Campaign',
    'rejected': 'Rejected',
}

LEAD_STATUS_COLORS = {
    'new': '#6B7280',
    'enriching': '#F59E0B',
    'enriched': '#3B82F6',
    'qualified': '#8B5CF6',
    'approved': '#10B981',
    'in_campaign': '#059669',
    'rejected': '#EF4444',
}


class Lead(db.Model):
    __tablename__ = 'leads'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=True, index=True)

    # Business info (from Google Places / Map Explorer)
    name = db.Column(db.String(200), nullable=False)
    address = db.Column(db.String(500))
    phone = db.Column(db.String(50))
    website = db.Column(db.String(255))
    place_id = db.Column(db.String(100))
    google_rating = db.Column(db.Float)
    review_count = db.Column(db.Integer)
    business_category = db.Column(db.String(200))
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)

    # Enrichment data
    employee_count = db.Column(db.Integer)
    employee_count_source = db.Column(db.String(50))  # linkedin, website, google
    linkedin_url = db.Column(db.String(500))
    emails_found = db.Column(db.Text)  # JSON array of emails scraped from website
    decision_maker = db.Column(db.String(200))  # Name of owner/decision-maker if found
    year_founded = db.Column(db.String(10))
    enrichment_data = db.Column(db.Text)  # JSON blob for extra data

    # Cowork M&A enrichment fields
    location_count = db.Column(db.Integer)  # Number of business locations detected
    total_review_volume = db.Column(db.Integer)  # Google + Yelp reviews combined
    review_velocity = db.Column(db.Float)  # Reviews per year (growth proxy)
    years_in_operation = db.Column(db.Integer)  # Computed from license date or year_founded
    license_number = db.Column(db.String(100))
    license_status = db.Column(db.String(50))  # active, expired, suspended
    license_issue_date = db.Column(db.Date)
    owner_name = db.Column(db.String(200))  # From license records or website
    data_sources = db.Column(db.Text)  # JSON array: ["google", "yelp", "cslb_ca"]
    thesis_fit_score = db.Column(db.Integer)  # 0-100, scored against acquisition thesis

    # Scoring
    score = db.Column(db.Integer)  # 0-100
    score_breakdown = db.Column(db.Text)  # JSON

    # Retirement likelihood detection
    retirement_score = db.Column(db.Integer)  # 0-100, NULL = not assessed
    retirement_label = db.Column(db.String(20))  # 'high', 'medium', 'low', 'unknown'

    # Pipeline status
    status = db.Column(db.String(20), default='new', index=True)
    source = db.Column(db.String(50), default='map_explorer')  # map_explorer, discovery, manual

    # Conversion tracking
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    enriched_at = db.Column(db.DateTime)
    approved_at = db.Column(db.DateTime)

    def get_emails_found(self):
        if not self.emails_found:
            return []
        try:
            return json.loads(self.emails_found)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_emails_found(self, emails):
        self.emails_found = json.dumps(emails) if emails else None

    def get_enrichment_data(self):
        if not self.enrichment_data:
            return {}
        try:
            return json.loads(self.enrichment_data)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_enrichment_data(self, data):
        self.enrichment_data = json.dumps(data) if data else None

    def get_score_breakdown(self):
        if not self.score_breakdown:
            return {}
        try:
            return json.loads(self.score_breakdown)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_score_breakdown(self, data):
        """Store score breakdown as JSON."""
        self.score_breakdown = json.dumps(data) if data else None

    def get_data_sources(self):
        """Return parsed data sources list or empty list."""
        if not self.data_sources:
            return []
        try:
            return json.loads(self.data_sources)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_data_sources(self, sources):
        """Store data sources list as JSON."""
        self.data_sources = json.dumps(sources) if sources else None

    def to_dict(self):
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'name': self.name,
            'address': self.address,
            'phone': self.phone,
            'website': self.website,
            'place_id': self.place_id,
            'google_rating': self.google_rating,
            'review_count': self.review_count,
            'business_category': self.business_category,
            'lat': self.lat,
            'lng': self.lng,
            'employee_count': self.employee_count,
            'employee_count_source': self.employee_count_source,
            'linkedin_url': self.linkedin_url,
            'emails_found': self.get_emails_found(),
            'decision_maker': self.decision_maker,
            'year_founded': self.year_founded,
            'enrichment_data': self.get_enrichment_data(),
            'score': self.score,
            'score_breakdown': self.get_score_breakdown(),
            'retirement_score': self.retirement_score,
            'retirement_label': self.retirement_label,
            'status': self.status,
            'status_label': LEAD_STATUS_LABELS.get(self.status, 'New'),
            'status_color': LEAD_STATUS_COLORS.get(self.status, '#6B7280'),
            'source': self.source,
            'campaign_id': self.campaign_id,
            'contact_id': self.contact_id,
            'location_count': self.location_count,
            'total_review_volume': self.total_review_volume,
            'review_velocity': self.review_velocity,
            'years_in_operation': self.years_in_operation,
            'license_number': self.license_number,
            'license_status': self.license_status,
            'license_issue_date': self.license_issue_date.isoformat() if self.license_issue_date else None,
            'owner_name': self.owner_name,
            'data_sources': self.get_data_sources(),
            'thesis_fit_score': self.thesis_fit_score,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'enriched_at': self.enriched_at.isoformat() if self.enriched_at else None,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
        }
