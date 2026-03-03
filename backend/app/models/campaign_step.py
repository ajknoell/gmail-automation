from app import db
from datetime import datetime


class CampaignStep(db.Model):
    __tablename__ = 'campaign_steps'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=False, index=True)
    position = db.Column(db.Integer, nullable=False, default=1)
    name = db.Column(db.String(100))

    # Content source: 'template' or 'ai_followup'
    step_type = db.Column(db.String(20), nullable=False, default='template')

    # If step_type == 'template'
    template_id = db.Column(db.Integer, db.ForeignKey('templates.id'), nullable=True)

    # If step_type == 'ai_followup'
    ai_prompt = db.Column(db.Text)
    use_web_research = db.Column(db.Boolean, default=False)
    web_research_prompt = db.Column(db.Text)

    # Delay before this step fires (days after previous step's send per recipient)
    delay_days = db.Column(db.Integer, default=3)  # legacy — kept for backward compat
    # Flexible delay in minutes (0 = immediate, 60 = 1 hour, 1440 = 1 day, 4320 = 3 days)
    delay_minutes = db.Column(db.Integer, default=4320)

    # A/B testing fields
    variant_group = db.Column(db.String(50), nullable=True)   # groups variant steps together
    variant_label = db.Column(db.String(20), nullable=True)    # e.g., 'A', 'B'
    variant_pct = db.Column(db.Integer, nullable=True)         # percentage allocation

    # Whether to auto-send when due or require manual approval
    auto_send = db.Column(db.Boolean, default=False)

    # Status tracking
    status = db.Column(db.String(20), default='draft')  # draft, generating, ready, running, completed, cancelled

    # Counts
    total_recipients = db.Column(db.Integer, default=0)
    sent_count = db.Column(db.Integer, default=0)
    failed_count = db.Column(db.Integer, default=0)
    skipped_count = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)

    # Relationships
    template = db.relationship('Template', foreign_keys=[template_id])
    step_recipients = db.relationship('StepRecipient', backref='step', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def effective_delay_minutes(self):
        """Return delay in minutes, preferring delay_minutes, falling back to delay_days."""
        if self.delay_minutes is not None:
            return self.delay_minutes
        return (self.delay_days or 3) * 1440

    def to_dict(self):
        return {
            'id': self.id,
            'campaign_id': self.campaign_id,
            'position': self.position,
            'name': self.name or f'Step {self.position}',
            'step_type': self.step_type,
            'template_id': self.template_id,
            'ai_prompt': self.ai_prompt,
            'use_web_research': self.use_web_research,
            'web_research_prompt': self.web_research_prompt,
            'delay_days': self.delay_days,
            'delay_minutes': self.delay_minutes,
            'effective_delay_minutes': self.effective_delay_minutes,
            'variant_group': self.variant_group,
            'variant_label': self.variant_label,
            'variant_pct': self.variant_pct,
            'auto_send': self.auto_send,
            'status': self.status,
            'total_recipients': self.total_recipients,
            'sent_count': self.sent_count,
            'failed_count': self.failed_count,
            'skipped_count': self.skipped_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }
