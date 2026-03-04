"""
Acquisition Thesis — defines a buy-side investment thesis for a specific
vertical/geography. Cowork generates and maintains the thesis document;
Claude Code stores it and scores leads against the criteria.
"""
import json
from datetime import datetime

from app import db


THESIS_STATUSES = ['active', 'paused', 'archived']


class AcquisitionThesis(db.Model):
    """A buy-side acquisition thesis with scoring criteria and strategy document."""

    __tablename__ = 'acquisition_theses'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)

    # Identity
    name = db.Column(db.String(200), nullable=False)
    vertical = db.Column(db.String(100))  # "HVAC", "Plumbing", "Electrical"
    status = db.Column(db.String(20), default='active')

    # Size criteria (employee count as primary proxy for revenue)
    min_employee_count = db.Column(db.Integer)
    max_employee_count = db.Column(db.Integer)

    # Maturity criteria
    min_years_in_operation = db.Column(db.Integer)
    max_years_in_operation = db.Column(db.Integer)

    # Scale criteria
    min_location_count = db.Column(db.Integer)
    max_location_count = db.Column(db.Integer)

    # Revenue proxy
    min_review_volume = db.Column(db.Integer)

    # Geography and category targeting (JSON arrays)
    target_geographies = db.Column(db.Text)  # ["California", "Texas", "Florida"]
    target_categories = db.Column(db.Text)   # ["HVAC", "plumbing", "electrical"]
    exclude_categories = db.Column(db.Text)  # ["residential only", ...]

    # Thesis document (Cowork-generated, human-approved)
    thesis_document = db.Column(db.Text)  # Markdown: opportunity, why-now, pros, cons, recommendation
    thesis_updated_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def _parse_json_list(self, field_value: str | None) -> list:
        """Parse a JSON text column as a list, returning empty list on failure."""
        if not field_value:
            return []
        try:
            return json.loads(field_value)
        except (json.JSONDecodeError, TypeError):
            return []

    def get_target_geographies(self) -> list:
        """Return parsed target geographies list."""
        return self._parse_json_list(self.target_geographies)

    def get_target_categories(self) -> list:
        """Return parsed target categories list."""
        return self._parse_json_list(self.target_categories)

    def get_exclude_categories(self) -> list:
        """Return parsed exclude categories list."""
        return self._parse_json_list(self.exclude_categories)

    def to_dict(self) -> dict:
        """Serialize thesis to dictionary."""
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'name': self.name,
            'vertical': self.vertical,
            'status': self.status,
            'min_employee_count': self.min_employee_count,
            'max_employee_count': self.max_employee_count,
            'min_years_in_operation': self.min_years_in_operation,
            'max_years_in_operation': self.max_years_in_operation,
            'min_location_count': self.min_location_count,
            'max_location_count': self.max_location_count,
            'min_review_volume': self.min_review_volume,
            'target_geographies': self.get_target_geographies(),
            'target_categories': self.get_target_categories(),
            'exclude_categories': self.get_exclude_categories(),
            'thesis_document': self.thesis_document,
            'thesis_updated_at': self.thesis_updated_at.isoformat() if self.thesis_updated_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
