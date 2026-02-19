"""
Feature visibility API endpoints.
Allows managing per-workspace feature toggles.
"""

from flask import Blueprint, request, jsonify, g
from app.services.feature_service import (
    get_all_features,
    is_feature_enabled,
    get_enabled_features,
    set_feature_visibility,
    get_features_with_status,
    FEATURES,
)

features_bp = Blueprint('features', __name__)


@features_bp.route('', methods=['GET'])
@features_bp.route('/', methods=['GET'])
def list_all_features():
    """Get all available features with metadata."""
    features = get_all_features()
    result = {
        name: {
            'display_name': metadata['display_name'],
            'enabled_by_default': metadata['enabled_by_default'],
        }
        for name, metadata in features.items()
    }
    return jsonify(result)


@features_bp.route('/enabled', methods=['GET'])
def list_enabled_features():
    """Get enabled features for the current workspace."""
    if not g.workspace_id:
        return jsonify({'error': 'No workspace selected'}), 400

    enabled = get_enabled_features(g.workspace_id)
    return jsonify({'enabled_features': enabled})


@features_bp.route('/<feature_name>/visibility', methods=['PUT'])
def update_feature_visibility(feature_name):
    """Toggle feature visibility for the current workspace."""
    if not g.workspace_id:
        return jsonify({'error': 'No workspace selected'}), 400

    if feature_name not in FEATURES:
        return jsonify({'error': f'Unknown feature: {feature_name}'}), 404

    data = request.get_json() or {}
    enabled = data.get('enabled', True)

    try:
        set_feature_visibility(g.workspace_id, feature_name, enabled)
        return jsonify({
            'feature': feature_name,
            'enabled': enabled,
            'workspace_id': g.workspace_id,
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@features_bp.route('/status', methods=['GET'])
def get_workspace_features_status():
    """Get all features with their current enabled status for the workspace."""
    if not g.workspace_id:
        return jsonify({'error': 'No workspace selected'}), 400

    features = get_features_with_status(g.workspace_id)
    return jsonify(features)
