from app import db
from datetime import datetime
import json as _json

class Campaign(db.Model):
    __tablename__ = 'campaigns'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=True, index=True)
    name = db.Column(db.String(100), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('templates.id'))
    gmail_account_id = db.Column(db.Integer, db.ForeignKey('oauth_tokens.id'))
    status = db.Column(db.String(20), default='draft')  # draft, running, paused, completed, cancelled, sequence_active
    total_recipients = db.Column(db.Integer, default=0)
    sent_count = db.Column(db.Integer, default=0)
    failed_count = db.Column(db.Integer, default=0)
    delay_seconds = db.Column(db.Integer, default=30)
    use_ai_personalization = db.Column(db.Boolean, default=True)
    ai_prompt = db.Column(db.Text)  # Special instructions for AI
    campaign_context = db.Column(db.Text)  # Things to include in every email for this campaign
    competitor_search_query = db.Column(db.Text)  # Google Places query for competitor discovery; None = disabled
    attachments = db.Column(db.Text)  # JSON array of attachment metadata
    auto_send_enabled = db.Column(db.Boolean, default=False)
    auto_send_threshold = db.Column(db.Float, default=0.8)
    archetype_id = db.Column(db.Integer, db.ForeignKey('outreach_archetypes.id'), nullable=True)
    thesis_id = db.Column(db.Integer, db.ForeignKey('acquisition_theses.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)

    recipients = db.relationship('Recipient', backref='campaign', lazy='dynamic', cascade='all, delete-orphan')
    email_logs = db.relationship('EmailLog', backref='campaign', lazy='dynamic', cascade='all, delete-orphan')
    gmail_account = db.relationship('OAuthToken', foreign_keys=[gmail_account_id])
    steps = db.relationship('CampaignStep', backref='campaign', lazy='dynamic',
                            cascade='all, delete-orphan',
                            order_by='CampaignStep.position')

    def to_dict(self, include_template=False, include_steps=False):
        data = {
            'id': self.id,
            'name': self.name,
            'template_id': self.template_id,
            'gmail_account_id': self.gmail_account_id,
            'gmail_account_email': self.gmail_account.email_address if self.gmail_account else None,
            'status': self.status,
            'total_recipients': self.total_recipients,
            'sent_count': self.sent_count,
            'failed_count': self.failed_count,
            'delay_seconds': self.delay_seconds,
            'use_ai_personalization': self.use_ai_personalization,
            'ai_prompt': self.ai_prompt,
            'campaign_context': self.campaign_context,
            'competitor_search_query': self.competitor_search_query,
            'attachments': self.get_attachments(),
            'auto_send_enabled': self.auto_send_enabled or False,
            'auto_send_threshold': self.auto_send_threshold if self.auto_send_threshold is not None else 0.8,
            'archetype_id': self.archetype_id,
            'thesis_id': self.thesis_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }
        if include_template and self.template:
            data['template'] = self.template.to_dict()
        if include_steps:
            data['steps'] = [s.to_dict() for s in self.steps.order_by('position').all()]
        return data

    def get_attachments(self):
        """Return parsed attachments list or empty list."""
        if self.attachments:
            try:
                return _json.loads(self.attachments)
            except Exception:
                pass
        return []

    def set_attachments(self, att_list):
        """Store attachments list as JSON."""
        self.attachments = _json.dumps(att_list) if att_list else None
