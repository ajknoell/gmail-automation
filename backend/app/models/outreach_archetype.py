"""
Outreach Archetype — personalization strategy set once at the archetype level
by Cowork. Owner-operators in trades/services respond to life and lifestyle
triggers, not product or technical ones. Individual personalization is light:
business name, geography, one specific operational detail.
"""
import json
from datetime import datetime

from app import db


class OutreachArchetype(db.Model):
    """A reusable outreach personalization strategy for a target archetype."""

    __tablename__ = 'outreach_archetypes'

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False, index=True)
    thesis_id = db.Column(db.Integer, db.ForeignKey('acquisition_theses.id'), nullable=True)

    # Identity
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)

    # Personalization strategy (Cowork-authored)
    tone = db.Column(db.String(50))  # "peer-to-peer", "professional", "casual"
    trigger_themes = db.Column(db.Text)  # JSON: ["years of ownership", "succession", "lifestyle change"]
    avoid_themes = db.Column(db.Text)   # JSON: ["product features", "technical specs", "ROI metrics"]
    value_proposition = db.Column(db.Text)  # Core message in Cowork's words
    subject_line_formula = db.Column(db.Text)  # e.g. "{{business_name}} — quick question about {{trigger}}"
    opening_formula = db.Column(db.Text)  # e.g. "I noticed {{operational_detail}} about {{business_name}}..."
    cta_style = db.Column(db.String(50))  # "soft-ask", "direct-meeting", "info-share"

    # Which personalization fields to include
    required_fields = db.Column(db.Text)  # JSON: ["business_name", "geography", "operational_detail"]
    optional_fields = db.Column(db.Text)  # JSON: ["years_in_business", "owner_name"]

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def _parse_json_list(self, field_value: str | None) -> list:
        """Parse a JSON text column as a list."""
        if not field_value:
            return []
        try:
            return json.loads(field_value)
        except (json.JSONDecodeError, TypeError):
            return []

    def get_trigger_themes(self) -> list:
        """Return parsed trigger themes."""
        return self._parse_json_list(self.trigger_themes)

    def get_avoid_themes(self) -> list:
        """Return parsed avoid themes."""
        return self._parse_json_list(self.avoid_themes)

    def get_required_fields(self) -> list:
        """Return parsed required personalization fields."""
        return self._parse_json_list(self.required_fields)

    def get_optional_fields(self) -> list:
        """Return parsed optional personalization fields."""
        return self._parse_json_list(self.optional_fields)

    def generate_ai_prompt(self) -> str:
        """Generate an AI personalization prompt from the archetype strategy.

        This is the bridge: Cowork writes the archetype once, every campaign
        using that archetype gets consistent personalization without manual
        prompt authoring.

        Returns:
            Prompt string for Claude email personalization.
        """
        parts = []

        parts.append(f"ARCHETYPE: {self.name}")
        if self.description:
            parts.append(f"CONTEXT: {self.description}")

        if self.tone:
            parts.append(f"TONE: Write in a {self.tone} tone.")

        triggers = self.get_trigger_themes()
        if triggers:
            parts.append(f"TRIGGER THEMES to reference: {', '.join(triggers)}")

        avoids = self.get_avoid_themes()
        if avoids:
            parts.append(f"AVOID these themes: {', '.join(avoids)}")

        if self.value_proposition:
            parts.append(f"CORE MESSAGE: {self.value_proposition}")

        if self.subject_line_formula:
            parts.append(f"SUBJECT LINE PATTERN: {self.subject_line_formula}")

        if self.opening_formula:
            parts.append(f"OPENING PATTERN: {self.opening_formula}")

        if self.cta_style:
            parts.append(f"CTA STYLE: {self.cta_style}")

        required = self.get_required_fields()
        if required:
            parts.append(f"MUST INCLUDE: {', '.join(required)}")

        optional = self.get_optional_fields()
        if optional:
            parts.append(f"OPTIONALLY INCLUDE (if available): {', '.join(optional)}")

        parts.append(
            "PERSONALIZATION LEVEL: Light touch — business name, geography, "
            "one specific operational detail. Do NOT over-research or over-personalize."
        )

        return '\n'.join(parts)

    def to_dict(self) -> dict:
        """Serialize archetype to dictionary."""
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'thesis_id': self.thesis_id,
            'name': self.name,
            'description': self.description,
            'tone': self.tone,
            'trigger_themes': self.get_trigger_themes(),
            'avoid_themes': self.get_avoid_themes(),
            'value_proposition': self.value_proposition,
            'subject_line_formula': self.subject_line_formula,
            'opening_formula': self.opening_formula,
            'cta_style': self.cta_style,
            'required_fields': self.get_required_fields(),
            'optional_fields': self.get_optional_fields(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
