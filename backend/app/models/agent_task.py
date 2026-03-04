"""
AgentTask — tracks execution of AI-powered agent tasks.
Stores config, results, execution logs, and cost metrics.
"""
import json
from app import db
from datetime import datetime


AGENT_TYPES = ['prospect_research', 'lead_discovery', 'competitive_intel']

AGENT_TYPE_LABELS = {
    'prospect_research': 'Prospect Research',
    'lead_discovery': 'Lead Discovery',
    'competitive_intel': 'Competitive Intelligence',
}

TASK_STATUSES = ['pending', 'running', 'completed', 'failed', 'cancelled']


class AgentTask(db.Model):
    __tablename__ = 'agent_tasks'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)

    # Agent classification
    agent_type = db.Column(db.String(50), nullable=False, index=True)
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)

    # Configuration (input params for the agent)
    config = db.Column(db.Text)  # JSON

    # Results
    result = db.Column(db.Text)  # JSON — structured output from the agent
    result_summary = db.Column(db.Text)  # Human-readable summary

    # Execution log (step-by-step tool calls)
    execution_log = db.Column(db.Text)  # JSON array

    # Cost tracking
    input_tokens = db.Column(db.Integer, default=0)
    output_tokens = db.Column(db.Integer, default=0)
    firecrawl_pages_scraped = db.Column(db.Integer, default=0)

    # Links to entities created/updated
    lead_id = db.Column(db.Integer, db.ForeignKey('leads.id'), nullable=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'), nullable=True)

    # Error info
    error_message = db.Column(db.Text)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)

    # JSON helpers
    def get_config(self):
        if not self.config:
            return {}
        try:
            return json.loads(self.config)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_config(self, data):
        self.config = json.dumps(data) if data else None

    def get_result(self):
        if not self.result:
            return {}
        try:
            return json.loads(self.result)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_result(self, data):
        self.result = json.dumps(data) if data else None

    def get_execution_log(self):
        if not self.execution_log:
            return []
        try:
            return json.loads(self.execution_log)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_execution_log(self, data):
        self.execution_log = json.dumps(data) if data else None

    def to_dict(self):
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'agent_type': self.agent_type,
            'agent_type_label': AGENT_TYPE_LABELS.get(self.agent_type, self.agent_type),
            'status': self.status,
            'config': self.get_config(),
            'result': self.get_result(),
            'result_summary': self.result_summary,
            'execution_log': self.get_execution_log(),
            'input_tokens': self.input_tokens,
            'output_tokens': self.output_tokens,
            'firecrawl_pages_scraped': self.firecrawl_pages_scraped,
            'lead_id': self.lead_id,
            'contact_id': self.contact_id,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }
