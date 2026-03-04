from app import db
from datetime import datetime

DEAL_STAGES = [
    'interested',
    'contacted_broker',
    'nda_signed',
    'reviewing_financials',
    'loi_submitted',
    'under_contract',
    'due_diligence',
    'closed_won',
    'closed_lost',
]

DEAL_STAGE_LABELS = {
    'interested': 'Interested',
    'contacted_broker': 'Contacted Broker',
    'nda_signed': 'NDA Signed',
    'reviewing_financials': 'Reviewing Financials',
    'loi_submitted': 'LOI Submitted',
    'under_contract': 'Under Contract',
    'due_diligence': 'Due Diligence',
    'closed_won': 'Closed Won',
    'closed_lost': 'Closed Lost',
}

DEAL_STAGE_COLORS = {
    'interested': '#6B7280',
    'contacted_broker': '#3B82F6',
    'nda_signed': '#8B5CF6',
    'reviewing_financials': '#F59E0B',
    'loi_submitted': '#E8603C',
    'under_contract': '#D97706',
    'due_diligence': '#0891B2',
    'closed_won': '#10B981',
    'closed_lost': '#EF4444',
}


class Deal(db.Model):
    __tablename__ = 'deals'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)

    # Core info
    name = db.Column(db.String(300), nullable=False)
    stage = db.Column(db.String(30), default='interested', index=True)

    # Foreign keys (nullable — deals can exist independently)
    listing_id = db.Column(db.Integer, db.ForeignKey('listings.id'), nullable=True, index=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=True, index=True)

    # Financial fields
    asking_price = db.Column(db.Float)
    offer_price = db.Column(db.Float)
    revenue = db.Column(db.Float)
    cash_flow = db.Column(db.Float)
    sde = db.Column(db.Float)
    ebitda = db.Column(db.Float)

    # Broker info
    broker_name = db.Column(db.String(200))
    broker_email = db.Column(db.String(255))
    broker_phone = db.Column(db.String(50))

    # Metadata
    source = db.Column(db.String(100))
    url = db.Column(db.String(500))
    location = db.Column(db.String(300))
    category = db.Column(db.String(200))
    notes = db.Column(db.Text)

    # Dates
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    stage_changed_at = db.Column(db.DateTime, default=datetime.utcnow)
    expected_close_date = db.Column(db.Date)

    # Relationships
    listing = db.relationship('Listing', backref='deals', lazy='select')
    contact = db.relationship('Contact', backref='deals', lazy='select')

    def to_dict(self):
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'name': self.name,
            'stage': self.stage,
            'stage_label': DEAL_STAGE_LABELS.get(self.stage, self.stage),
            'stage_color': DEAL_STAGE_COLORS.get(self.stage, '#6B7280'),
            'listing_id': self.listing_id,
            'listing_name': self.listing.title if self.listing else None,
            'contact_id': self.contact_id,
            'contact_name': self.contact.name if self.contact else None,
            'contact_email': self.contact.email if self.contact else None,
            'asking_price': self.asking_price,
            'offer_price': self.offer_price,
            'revenue': self.revenue,
            'cash_flow': self.cash_flow,
            'sde': self.sde,
            'ebitda': self.ebitda,
            'broker_name': self.broker_name,
            'broker_email': self.broker_email,
            'broker_phone': self.broker_phone,
            'source': self.source,
            'url': self.url,
            'location': self.location,
            'category': self.category,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'stage_changed_at': self.stage_changed_at.isoformat() if self.stage_changed_at else None,
            'expected_close_date': self.expected_close_date.isoformat() if self.expected_close_date else None,
        }
