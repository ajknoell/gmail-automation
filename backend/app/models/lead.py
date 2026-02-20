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

    # Scoring
    score = db.Column(db.Integer)  # 0-100
    score_breakdown = db.Column(db.Text)  # JSON

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
        self.score_breakdown = json.dumps(data) if data else None

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
            'status': self.status,
            'status_label': LEAD_STATUS_LABELS.get(self.status, 'New'),
            'status_color': LEAD_STATUS_COLORS.get(self.status, '#6B7280'),
            'source': self.source,
            'campaign_id': self.campaign_id,
            'contact_id': self.contact_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'enriched_at': self.enriched_at.isoformat() if self.enriched_at else None,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
        }
