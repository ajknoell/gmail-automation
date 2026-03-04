"""
Acquisition Thesis routes — CRUD for buy-side investment theses
and thesis-aware lead ranking.
"""
import json
from datetime import datetime

from flask import Blueprint, request, jsonify, g

from app import db
from app.models.acquisition_thesis import AcquisitionThesis, THESIS_STATUSES

thesis_bp = Blueprint('thesis', __name__)


@thesis_bp.route('/', methods=['GET'])
def list_theses() -> tuple:
    """List all acquisition theses for the workspace."""
    status = request.args.get('status')
    query = AcquisitionThesis.query.filter_by(workspace_id=g.workspace_id)
    if status and status in THESIS_STATUSES:
        query = query.filter_by(status=status)
    theses = query.order_by(AcquisitionThesis.updated_at.desc()).all()
    return jsonify({'theses': [t.to_dict() for t in theses]})


@thesis_bp.route('/<int:thesis_id>', methods=['GET'])
def get_thesis(thesis_id: int) -> tuple:
    """Get a single thesis by ID."""
    thesis = AcquisitionThesis.query.get(thesis_id)
    if not thesis or thesis.workspace_id != g.workspace_id:
        return jsonify({'error': 'Thesis not found'}), 404
    return jsonify(thesis.to_dict())


@thesis_bp.route('/', methods=['POST'])
def create_thesis() -> tuple:
    """Create a new acquisition thesis."""
    data = request.get_json() or {}

    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Thesis name is required'}), 400

    status = data.get('status', 'active')
    if status not in THESIS_STATUSES:
        return jsonify({'error': f'Invalid status. Must be one of: {", ".join(THESIS_STATUSES)}'}), 400

    thesis = AcquisitionThesis(
        workspace_id=g.workspace_id,
        name=name,
        vertical=data.get('vertical'),
        status=status,
        min_employee_count=data.get('min_employee_count'),
        max_employee_count=data.get('max_employee_count'),
        min_years_in_operation=data.get('min_years_in_operation'),
        max_years_in_operation=data.get('max_years_in_operation'),
        min_location_count=data.get('min_location_count'),
        max_location_count=data.get('max_location_count'),
        min_review_volume=data.get('min_review_volume'),
        thesis_document=data.get('thesis_document'),
    )

    # Store JSON array fields
    if data.get('target_geographies'):
        thesis.target_geographies = json.dumps(data['target_geographies'])
    if data.get('target_categories'):
        thesis.target_categories = json.dumps(data['target_categories'])
    if data.get('exclude_categories'):
        thesis.exclude_categories = json.dumps(data['exclude_categories'])

    if thesis.thesis_document:
        thesis.thesis_updated_at = datetime.utcnow()

    db.session.add(thesis)
    db.session.commit()
    return jsonify(thesis.to_dict()), 201


@thesis_bp.route('/<int:thesis_id>', methods=['PUT'])
def update_thesis(thesis_id: int) -> tuple:
    """Update an existing thesis."""
    thesis = AcquisitionThesis.query.get(thesis_id)
    if not thesis or thesis.workspace_id != g.workspace_id:
        return jsonify({'error': 'Thesis not found'}), 404

    data = request.get_json() or {}

    if 'status' in data and data['status'] not in THESIS_STATUSES:
        return jsonify({'error': f'Invalid status. Must be one of: {", ".join(THESIS_STATUSES)}'}), 400

    # Simple scalar fields
    scalar_fields = [
        'name', 'vertical', 'status',
        'min_employee_count', 'max_employee_count',
        'min_years_in_operation', 'max_years_in_operation',
        'min_location_count', 'max_location_count',
        'min_review_volume',
    ]
    for field in scalar_fields:
        if field in data:
            setattr(thesis, field, data[field])

    # JSON array fields
    for json_field in ['target_geographies', 'target_categories', 'exclude_categories']:
        if json_field in data:
            setattr(thesis, json_field, json.dumps(data[json_field]) if data[json_field] else None)

    # Thesis document (track update time)
    if 'thesis_document' in data:
        thesis.thesis_document = data['thesis_document']
        thesis.thesis_updated_at = datetime.utcnow()

    db.session.commit()
    return jsonify(thesis.to_dict())


@thesis_bp.route('/<int:thesis_id>', methods=['DELETE'])
def delete_thesis(thesis_id: int) -> tuple:
    """Delete a thesis."""
    thesis = AcquisitionThesis.query.get(thesis_id)
    if not thesis or thesis.workspace_id != g.workspace_id:
        return jsonify({'error': 'Thesis not found'}), 404
    db.session.delete(thesis)
    db.session.commit()
    return jsonify({'success': True})


@thesis_bp.route('/<int:thesis_id>/targets', methods=['GET'])
def get_thesis_targets(thesis_id: int) -> tuple:
    """Get leads ranked by thesis fit score."""
    thesis = AcquisitionThesis.query.get(thesis_id)
    if not thesis or thesis.workspace_id != g.workspace_id:
        return jsonify({'error': 'Thesis not found'}), 404

    from app.services.thesis_scorer import ThesisScorer

    min_score = request.args.get('min_score', 0, type=int)
    limit = request.args.get('limit', 50, type=int)
    limit = min(limit, 200)

    ranked = ThesisScorer.rank_leads(g.workspace_id, thesis_id, limit=limit, min_score=min_score)
    return jsonify({
        'thesis_id': thesis_id,
        'thesis_name': thesis.name,
        'targets': ranked,
        'count': len(ranked),
    })
