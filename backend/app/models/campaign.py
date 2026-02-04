from app import db
from datetime import datetime

class Campaign(db.Model):
    __tablename__ = 'campaigns'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('templates.id'))
    status = db.Column(db.String(20), default='draft')  # draft, running, paused, completed, cancelled
    total_recipients = db.Column(db.Integer, default=0)
    sent_count = db.Column(db.Integer, default=0)
    failed_count = db.Column(db.Integer, default=0)
    delay_seconds = db.Column(db.Integer, default=30)
    use_ai_personalization = db.Column(db.Boolean, default=True)
    ai_prompt = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)

    recipients = db.relationship('Recipient', backref='campaign', lazy='dynamic', cascade='all, delete-orphan')
    email_logs = db.relationship('EmailLog', backref='campaign', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self, include_template=False):
        data = {
            'id': self.id,
            'name': self.name,
            'template_id': self.template_id,
            'status': self.status,
            'total_recipients': self.total_recipients,
            'sent_count': self.sent_count,
            'failed_count': self.failed_count,
            'delay_seconds': self.delay_seconds,
            'use_ai_personalization': self.use_ai_personalization,
            'ai_prompt': self.ai_prompt,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }
        if include_template and self.template:
            data['template'] = self.template.to_dict()
        return data
