from app import db
from datetime import datetime


class MonitoredSite(db.Model):
    __tablename__ = 'monitored_sites'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=True, index=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=True)

    name = db.Column(db.String(200))  # e.g. "NJ Broker Plus"
    url = db.Column(db.String(500), nullable=False)  # The listings page URL to scrape
    scraper_type = db.Column(db.String(50), default='auto')  # 'auto', 'generic', 'njbrokerplus', 'aspira', etc.
    is_active = db.Column(db.Boolean, default=True)

    check_interval_hours = db.Column(db.Integer, default=24)  # How often to check
    last_checked_at = db.Column(db.DateTime)
    last_error = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    contact = db.relationship('Contact', backref='monitored_sites')
    listings = db.relationship('Listing', backref='site', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'contact_id': self.contact_id,
            'contact': self.contact.to_dict() if self.contact else None,
            'name': self.name,
            'url': self.url,
            'scraper_type': self.scraper_type,
            'is_active': self.is_active,
            'check_interval_hours': self.check_interval_hours,
            'last_checked_at': self.last_checked_at.isoformat() if self.last_checked_at else None,
            'last_error': self.last_error,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'listing_count': self.listings.count(),
            'new_listing_count': self.listings.filter_by(is_new=True).count(),
        }
