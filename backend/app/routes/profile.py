"""
Business Profile routes — manage the workspace's business identity,
capabilities, and target market for signal relevance scoring.
"""
from flask import Blueprint, request, jsonify, g
from app import db
import json

profile_bp = Blueprint('profile', __name__)


@profile_bp.route('', methods=['GET'])
def get_profile():
    """Get business profile for current workspace (creates empty if missing)."""
    from app.services.profile_service import ProfileService

    profile = ProfileService.get_profile(g.workspace_id)
    return jsonify(profile.to_dict())


@profile_bp.route('', methods=['PUT'])
def update_profile():
    """Update business profile."""
    from app.models.business_profile import BusinessProfile

    data = request.json or {}

    # Basic payload size validation
    raw = json.dumps(data)
    if len(raw) > 500_000:
        return jsonify({'error': 'Profile data too large (max 500KB)'}), 400

    profile = BusinessProfile.query.filter_by(workspace_id=g.workspace_id).first()
    if not profile:
        profile = BusinessProfile(workspace_id=g.workspace_id)
        db.session.add(profile)

    if 'company_name' in data:
        val = data['company_name']
        if not isinstance(val, str) or len(val) > 200:
            return jsonify({'error': 'company_name must be string <= 200 chars'}), 400
        profile.company_name = val
    if 'domain' in data:
        val = data['domain']
        if not isinstance(val, str) or len(val) > 200:
            return jsonify({'error': 'domain must be string <= 200 chars'}), 400
        profile.domain = val
    if 'tagline' in data:
        val = data['tagline']
        if not isinstance(val, str) or len(val) > 500:
            return jsonify({'error': 'tagline must be string <= 500 chars'}), 400
        profile.tagline = val
    if 'description' in data:
        val = data['description']
        if not isinstance(val, str) or len(val) > 5000:
            return jsonify({'error': 'description must be string <= 5000 chars'}), 400
        profile.description = val
    if 'capabilities' in data:
        val = data['capabilities']
        if not isinstance(val, list) or len(val) > 50:
            return jsonify({'error': 'capabilities must be a list (max 50)'}), 400
        profile.capabilities = json.dumps(val)
    if 'target_market' in data:
        val = data['target_market']
        if not isinstance(val, dict):
            return jsonify({'error': 'target_market must be an object'}), 400
        profile.target_market = json.dumps(val)
    if 'keywords' in data:
        val = data['keywords']
        if not isinstance(val, list) or len(val) > 100:
            return jsonify({'error': 'keywords must be a list (max 100)'}), 400
        profile.keywords = json.dumps(val)

    db.session.commit()
    return jsonify(profile.to_dict())
