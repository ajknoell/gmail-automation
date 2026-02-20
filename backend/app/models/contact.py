from app import db
from datetime import datetime

# Valid statuses for the pipeline
CONTACT_STATUSES = ['discovered', 'new', 'contacted', 'replied', 'interested', 'client', 'lost']

STATUS_LABELS = {
    'discovered': 'Discovered',
    'new': 'New Lead',
    'contacted': 'Contacted',
    'replied': 'Replied',
    'interested': 'Interested',
    'client': 'Client',
    'lost': 'Lost',
}

STATUS_COLORS = {
    'discovered': '#A855F7',
    'new': '#6B7280',
    'contacted': '#3B82F6',
    'replied': '#8B5CF6',
    'interested': '#F59E0B',
    'client': '#10B981',
    'lost': '#EF4444',
}


class Contact(db.Model):
    __tablename__ = 'contacts'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=True, index=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    name = db.Column(db.String(100))
    company = db.Column(db.String(100))
    website = db.Column(db.String(255))
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='new')

    # Discovery fields
    discovery_source = db.Column(db.String(50))  # google_maps, directory, website_scrape, manual
    discovered_at = db.Column(db.DateTime)
    google_rating = db.Column(db.Float)
    review_count = db.Column(db.Integer)
    phone = db.Column(db.String(50))
    address = db.Column(db.String(500))
    business_category = db.Column(db.String(200))
    qualified = db.Column(db.Boolean)
    qualification_reason = db.Column(db.Text)
    discovery_criteria_id = db.Column(db.Integer)

    # Follow-up tracking
    follow_up_date = db.Column(db.Date)
    follow_up_note = db.Column(db.Text)

    # Cached stats
    first_contacted_at = db.Column(db.DateTime)
    last_contacted_at = db.Column(db.DateTime)
    total_emails_sent = db.Column(db.Integer, default=0)
    last_replied_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Tags relationship
    tags = db.relationship('Tag', secondary='contact_tags', back_populates='contacts', lazy='select')

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'company': self.company,
            'website': self.website,
            'notes': self.notes,
            'status': self.status or 'new',
            'status_label': STATUS_LABELS.get(self.status or 'new', 'New Lead'),
            'status_color': STATUS_COLORS.get(self.status or 'new', '#6B7280'),
            'tags': [t.to_dict() for t in self.tags],
            'first_contacted_at': self.first_contacted_at.isoformat() if self.first_contacted_at else None,
            'last_contacted_at': self.last_contacted_at.isoformat() if self.last_contacted_at else None,
            'total_emails_sent': self.total_emails_sent or 0,
            'follow_up_date': self.follow_up_date.isoformat() if self.follow_up_date else None,
            'follow_up_note': self.follow_up_note,
            'last_replied_at': self.last_replied_at.isoformat() if self.last_replied_at else None,
            'discovery_source': self.discovery_source,
            'discovered_at': self.discovered_at.isoformat() if self.discovered_at else None,
            'google_rating': self.google_rating,
            'review_count': self.review_count,
            'phone': self.phone,
            'address': self.address,
            'business_category': self.business_category,
            'qualified': self.qualified,
            'qualification_reason': self.qualification_reason,
            'discovery_criteria_id': self.discovery_criteria_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def upsert_from_send(email, name=None, company=None, website=None, workspace_id=None):
        """Create or update a contact when an email is sent."""
        if not email:
            return None

        email = email.strip().lower()
        filters = {'email': email}
        if workspace_id:
            filters['workspace_id'] = workspace_id
        contact = Contact.query.filter_by(**filters).first()
        now = datetime.utcnow()

        if contact is None:
            contact = Contact(
                email=email,
                name=name or None,
                company=company or None,
                website=website or None,
                workspace_id=workspace_id,
                status='contacted',
                first_contacted_at=now,
                last_contacted_at=now,
                total_emails_sent=1,
            )
            db.session.add(contact)
        else:
            if name:
                contact.name = name
            if company:
                contact.company = company
            if website:
                contact.website = website
            contact.last_contacted_at = now
            contact.total_emails_sent = (contact.total_emails_sent or 0) + 1
            # Auto-advance status from 'new' to 'contacted' on send
            if contact.status == 'new':
                contact.status = 'contacted'

        return contact
