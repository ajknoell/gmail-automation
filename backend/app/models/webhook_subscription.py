"""
Webhook Subscription — allows external systems (Cowork) to receive
real-time notifications when key events occur in the platform.
"""
import json
from datetime import datetime

from app import db


WEBHOOK_EVENTS = [
    'reply.received',
    'reply.positive',
    'deal.stage_change',
    'target.discovered',
    'target.enriched',
    'campaign.completed',
    'report.weekly',
]


class WebhookSubscription(db.Model):
    """A webhook endpoint subscribed to platform events."""

    __tablename__ = 'webhook_subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)

    url = db.Column(db.String(500), nullable=False)
    events = db.Column(db.Text, nullable=False)  # JSON array of event types
    secret = db.Column(db.String(200))  # HMAC signing key
    is_active = db.Column(db.Boolean, default=True)

    # Tracking
    last_triggered_at = db.Column(db.DateTime)
    last_error = db.Column(db.Text)
    trigger_count = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_events(self) -> list[str]:
        """Return parsed events list."""
        if not self.events:
            return []
        try:
            return json.loads(self.events)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_events(self, events: list[str]) -> None:
        """Store events list as JSON."""
        self.events = json.dumps(events) if events else '[]'

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'url': self.url,
            'events': self.get_events(),
            'is_active': self.is_active,
            'last_triggered_at': self.last_triggered_at.isoformat() if self.last_triggered_at else None,
            'last_error': self.last_error,
            'trigger_count': self.trigger_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
