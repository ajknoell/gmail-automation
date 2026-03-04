"""
Feature visibility management service.
Handles per-workspace feature toggles using WorkspaceSettings.
"""

from app.models.settings import WorkspaceSettings

FEATURES = {
    'insights': {
        'display_name': 'Insights',
        'enabled_by_default': True,
    },
    'replies': {
        'display_name': 'Reply Hub',
        'enabled_by_default': True,
    },
    'quick_send': {
        'display_name': 'Quick Send',
        'enabled_by_default': True,
    },
    'campaigns': {
        'display_name': 'Campaigns',
        'enabled_by_default': True,
    },
    'follow_ups': {
        'display_name': 'Follow-up Steps',
        'enabled_by_default': True,
    },
    'templates': {
        'display_name': 'Templates',
        'enabled_by_default': True,
    },
    'contacts': {
        'display_name': 'Contacts',
        'enabled_by_default': True,
    },
    'listings': {
        'display_name': 'Listings',
        'enabled_by_default': True,
    },
    'cold_calls': {
        'display_name': 'Cold Calls',
        'enabled_by_default': True,
    },
}


def get_all_features():
    """
    Get all available features with metadata.

    Returns:
        dict: Feature definitions keyed by feature name
    """
    return FEATURES.copy()


def is_feature_enabled(workspace_id, feature_name):
    """
    Check if a feature is enabled for a workspace.

    Args:
        workspace_id: ID of the workspace
        feature_name: Name of the feature (key in FEATURES)

    Returns:
        bool: True if feature is enabled, False otherwise
    """
    if feature_name not in FEATURES:
        return False

    # Get the setting; if not set, use default from FEATURES
    setting_key = f'feature_visible_{feature_name}'
    value = WorkspaceSettings.get(workspace_id, setting_key, None)

    if value is None:
        # No setting found, use default
        return FEATURES[feature_name]['enabled_by_default']

    # Convert string 'true'/'false' to bool
    return value.lower() == 'true'


def get_enabled_features(workspace_id):
    """
    Get list of enabled feature names for a workspace.

    Args:
        workspace_id: ID of the workspace

    Returns:
        list: List of feature names that are enabled
    """
    enabled = []
    for feature_name in FEATURES.keys():
        if is_feature_enabled(workspace_id, feature_name):
            enabled.append(feature_name)
    return enabled


def set_feature_visibility(workspace_id, feature_name, enabled):
    """
    Set feature visibility for a workspace.

    Args:
        workspace_id: ID of the workspace
        feature_name: Name of the feature
        enabled: Boolean to enable/disable

    Raises:
        ValueError: If feature_name is not valid
    """
    if feature_name not in FEATURES:
        raise ValueError(f'Unknown feature: {feature_name}')

    setting_key = f'feature_visible_{feature_name}'
    value = 'true' if enabled else 'false'
    WorkspaceSettings.set(workspace_id, setting_key, value)


def get_features_with_status(workspace_id):
    """
    Get all features with their current enabled status for a workspace.

    Args:
        workspace_id: ID of the workspace

    Returns:
        dict: Features with name, display_name, and enabled status
    """
    features = {}
    for feature_name, metadata in FEATURES.items():
        features[feature_name] = {
            'display_name': metadata['display_name'],
            'enabled': is_feature_enabled(workspace_id, feature_name),
        }
    return features
