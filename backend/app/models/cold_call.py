from app import db
from datetime import datetime

COLD_CALL_OUTCOMES = [
    'connected',
    'voicemail',
    'no_answer',
    'callback_requested',
    'not_interested',
    'wrong_number',
    'other',
]

OUTCOME_LABELS = {
    'connected': 'Connected',
    'voicemail': 'Left Voicemail',
    'no_answer': 'No Answer',
    'callback_requested': 'Callback Requested',
    'not_interested': 'Not Interested',
    'wrong_number': 'Wrong Number',
    'other': 'Other',
}


class ColdCall(db.Model):
    __tablename__ = 'cold_calls'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=True, index=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=False, index=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id'), nullable=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('recipients.id'), nullable=True)

    call_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    outcome = db.Column(db.String(30), nullable=False, default='connected')
    notes = db.Column(db.Text)
    duration_minutes = db.Column(db.Integer)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    contact = db.relationship('Contact', backref=db.backref('cold_calls', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'contact_id': self.contact_id,
            'campaign_id': self.campaign_id,
            'recipient_id': self.recipient_id,
            'call_date': self.call_date.isoformat() if self.call_date else None,
            'outcome': self.outcome,
            'outcome_label': OUTCOME_LABELS.get(self.outcome, self.outcome),
            'notes': self.notes,
            'duration_minutes': self.duration_minutes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
