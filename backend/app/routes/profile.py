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

    profile = BusinessProfile.query.filter_by(workspace_id=g.workspace_id).first()
    if not profile:
        profile = BusinessProfile(workspace_id=g.workspace_id)
        db.session.add(profile)

    data = request.json or {}

    if 'company_name' in data:
        profile.company_name = data['company_name']
    if 'domain' in data:
        profile.domain = data['domain']
    if 'tagline' in data:
        profile.tagline = data['tagline']
    if 'description' in data:
        profile.description = data['description']
    if 'capabilities' in data:
        profile.capabilities = json.dumps(data['capabilities'])
    if 'target_market' in data:
        profile.target_market = json.dumps(data['target_market'])
    if 'keywords' in data:
        profile.keywords = json.dumps(data['keywords'])

    db.session.commit()
    return jsonify(profile.to_dict())
