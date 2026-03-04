"""
Outreach Archetype routes — CRUD for personalization strategies.
Cowork sets the archetype; Claude Code campaigns inherit it.
"""
import json

from flask import Blueprint, request, jsonify, g

from app import db
from app.models.outreach_archetype import OutreachArchetype

archetypes_bp = Blueprint('archetypes', __name__)


@archetypes_bp.route('/', methods=['GET'])
def list_archetypes() -> tuple:
    """List all outreach archetypes for the workspace."""
    query = OutreachArchetype.query.filter_by(workspace_id=g.workspace_id)

    thesis_id = request.args.get('thesis_id', type=int)
    if thesis_id:
        query = query.filter_by(thesis_id=thesis_id)

    archetypes = query.order_by(OutreachArchetype.updated_at.desc()).all()
    return jsonify({'archetypes': [a.to_dict() for a in archetypes]})


@archetypes_bp.route('/<int:archetype_id>', methods=['GET'])
def get_archetype(archetype_id: int) -> tuple:
    """Get a single archetype."""
    archetype = OutreachArchetype.query.get(archetype_id)
    if not archetype or archetype.workspace_id != g.workspace_id:
        return jsonify({'error': 'Archetype not found'}), 404
    return jsonify(archetype.to_dict())


@archetypes_bp.route('/', methods=['POST'])
def create_archetype() -> tuple:
    """Create a new outreach archetype."""
    data = request.get_json() or {}

    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Archetype name is required'}), 400

    archetype = OutreachArchetype(
        workspace_id=g.workspace_id,
        thesis_id=data.get('thesis_id'),
        name=name,
        description=data.get('description'),
        tone=data.get('tone'),
        value_proposition=data.get('value_proposition'),
        subject_line_formula=data.get('subject_line_formula'),
        opening_formula=data.get('opening_formula'),
        cta_style=data.get('cta_style'),
    )

    # JSON array fields
    for json_field in ['trigger_themes', 'avoid_themes', 'required_fields', 'optional_fields']:
        if data.get(json_field):
            setattr(archetype, json_field, json.dumps(data[json_field]))

    db.session.add(archetype)
    db.session.commit()
    return jsonify(archetype.to_dict()), 201


@archetypes_bp.route('/<int:archetype_id>', methods=['PUT'])
def update_archetype(archetype_id: int) -> tuple:
    """Update an existing archetype."""
    archetype = OutreachArchetype.query.get(archetype_id)
    if not archetype or archetype.workspace_id != g.workspace_id:
        return jsonify({'error': 'Archetype not found'}), 404

    data = request.get_json() or {}

    scalar_fields = [
        'name', 'description', 'thesis_id', 'tone',
        'value_proposition', 'subject_line_formula',
        'opening_formula', 'cta_style',
    ]
    for field in scalar_fields:
        if field in data:
            setattr(archetype, field, data[field])

    for json_field in ['trigger_themes', 'avoid_themes', 'required_fields', 'optional_fields']:
        if json_field in data:
            setattr(archetype, json_field, json.dumps(data[json_field]) if data[json_field] else None)

    db.session.commit()
    return jsonify(archetype.to_dict())


@archetypes_bp.route('/<int:archetype_id>', methods=['DELETE'])
def delete_archetype(archetype_id: int) -> tuple:
    """Delete an archetype."""
    archetype = OutreachArchetype.query.get(archetype_id)
    if not archetype or archetype.workspace_id != g.workspace_id:
        return jsonify({'error': 'Archetype not found'}), 404
    db.session.delete(archetype)
    db.session.commit()
    return jsonify({'success': True})


@archetypes_bp.route('/<int:archetype_id>/preview', methods=['GET'])
def preview_archetype(archetype_id: int) -> tuple:
    """Preview the AI prompt that would be generated from this archetype."""
    archetype = OutreachArchetype.query.get(archetype_id)
    if not archetype or archetype.workspace_id != g.workspace_id:
        return jsonify({'error': 'Archetype not found'}), 404

    return jsonify({
        'archetype_id': archetype.id,
        'archetype_name': archetype.name,
        'generated_ai_prompt': archetype.generate_ai_prompt(),
    })
