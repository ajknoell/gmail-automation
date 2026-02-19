# Implementation Plan: Workspace-Specific Feature Visibility

**Objective**: Enable selective feature hiding per workspace so certain features (like Listings) can be hidden for specific workspaces (e.g., construction website) while remaining visible in others (e.g., business outreach).

**Status**: Planned - Ready for implementation
**Scope**: Feature visibility control system with admin-only access and data preservation

---

## Problem Statement

Currently, all workspaces have access to all features. The user wants to:
- Hide the Listings tab/feature for the construction website workspace
- Add new features to the business outreach workspace that don't appear elsewhere
- Maintain clean, workspace-specific UIs

---

## Solution Overview

**Architecture**: Leverage existing `WorkspaceSettings` key-value table to store per-workspace feature visibility flags
**Data Preservation**: Disabling a feature hides it from UI but preserves database records
**Admin Control**: Only workspace admins can toggle feature visibility
**Location**: Feature visibility controls in existing Settings page

---

## Key Design Decisions

1. **Storage**: Use `WorkspaceSettings` (existing table) with keys like `feature_enabled_listings`
   - Avoids new migrations
   - Reuses proven unique constraint pattern: `(workspace_id, key)`
   - Scales to unlimited features

2. **Default Behavior**: All features enabled by default (opt-out model)
   - Backward compatible with existing workspaces
   - New workspaces have full feature access

3. **Data Handling**: Hide, don't delete
   - Disabling a feature hides UI but preserves database records
   - Re-enabling immediately restores access to all historical data
   - Optional: Users can manually archive/export data later

4. **Access Control**: Workspace admins only
   - Check authorization on API endpoints
   - Requires implementing/checking admin role logic
   - Protects feature visibility settings from non-admin users

5. **UI Location**: Feature Visibility section in existing Settings page
   - Integrated with workspace selector context
   - Shows feature status, data counts, and warnings

---

## Implementation Plan

### Phase 1: Backend Foundation (No User-Facing Changes)

#### B1: Create Feature Registry Service
**File**: `backend/app/services/feature_service.py` (NEW)

Create centralized feature registry with metadata:
```python
FEATURES = {
    'listings': {
        'name': 'listings',
        'display_name': 'Listings Monitor',
        'description': 'Monitor and track business listings from various sources',
        'route_path': '/listings',
        'blueprint_name': 'listings',
        'enabled_by_default': True,
        'data_tables': ['monitored_site', 'listing', 'deal_criteria'],
    },
    'insights': {
        'name': 'insights',
        'display_name': 'Insights & Analytics',
        'description': 'View campaign performance and email tracking analytics',
        'route_path': '/insights',
        'blueprint_name': 'insights',
        'enabled_by_default': True,
        'data_tables': [],  # Insights uses EmailLog but doesn't own it
    },
    'campaigns': {
        'name': 'campaigns',
        'display_name': 'Email Campaigns',
        'description': 'Create and manage multi-step email campaigns',
        'route_path': '/campaigns',
        'blueprint_name': 'campaigns',
        'enabled_by_default': True,
        'data_tables': ['campaign', 'campaign_step', 'recipient', 'email_log'],
    },
    # Add other features here...
}
```

Implement utility functions:
- `get_all_features()` - returns FEATURES dict
- `is_feature_enabled(workspace_id, feature_name)` - checks WorkspaceSettings, returns bool
- `get_enabled_features(workspace_id)` - returns list of enabled feature names
- `set_feature_visibility(workspace_id, feature_name, enabled)` - updates WorkspaceSettings
- `get_feature_info(feature_name)` - returns feature metadata

**Storage Pattern**:
- Key format: `feature_enabled_{feature_name}` (e.g., `feature_enabled_listings`)
- Value: `"true"` or `"false"` (stored as strings in WorkspaceSettings)
- Default (if key doesn't exist): enabled (`True`)

#### B2: Create Features API Blueprint
**File**: `backend/app/routes/features.py` (NEW)

Endpoints (all require workspace context via `g.workspace_id`):

1. **GET `/api/features`** - List all available features
   - Returns: `{ features: { "listings": {...}, "insights": {...}, ... } }`
   - Public endpoint (no auth required)

2. **GET `/api/features/workspace-enabled`** - Get enabled features for current workspace
   - Returns: `{ enabled_features: ["listings", "campaigns", ...], feature_info: {...} }`
   - Filters out disabled features
   - Used by frontend to decide what to render

3. **POST `/api/features/{feature_name}/visibility`** - Enable/disable a feature
   - Body: `{ "enabled": true/false }`
   - **REQUIRES ADMIN CHECK**: Verify current user is workspace admin
   - Returns: `{ feature: "listings", enabled: false }`
   - Returns 403 if user not admin

4. **GET `/api/features/{feature_name}/data-summary`** - Get record counts for a feature
   - Returns: `{ monitored_site: 5, listing: 234, deal_criteria: 1 }`
   - Shows user what data exists before disabling feature
   - **REQUIRES ADMIN CHECK**

#### B3: Register Features Blueprint
**File**: `backend/app/__init__.py` (MODIFY)

Add to app initialization:
```python
from app.routes.features import features_bp
app.register_blueprint(features_bp, url_prefix='/api/features')
```

#### B4: Add Admin Authorization Check
**File**: `backend/app/routes/features.py` (ADD)

Create helper function:
```python
def require_workspace_admin():
    """Check if current user is admin for current workspace."""
    # TODO: Implement based on your user/role system
    # Should check if current_user.is_admin or current_user.role == 'admin'
    # If not, abort(403)
    pass
```

Add to visibility endpoints:
```python
@features_bp.route('/<feature_name>/visibility', methods=['POST'])
def update_feature_visibility(feature_name):
    require_workspace_admin()  # Add this line
    # ... rest of endpoint
```

**Note**: Implementation depends on your existing user/role system. Look for:
- Current user identification (Flask-Login or similar)
- Workspace admin role/permission model
- If doesn't exist, decide: all users are admins, or only user who created workspace?

### Phase 2: Frontend Implementation

#### F1: Create Feature Visibility Hook
**File**: `frontend/src/hooks/useFeatureVisibility.js` (NEW)

```javascript
import { useEffect, useState } from 'react';
import { useWorkspace } from './useWorkspace';  // Assuming you have this
import * as api from '../api/client';

export const useFeatureVisibility = () => {
  const { workspaceId } = useWorkspace();
  const [enabledFeatures, setEnabledFeatures] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!workspaceId) return;

    setLoading(true);
    api.getWorkspaceFeaturesEnabled()
      .then(data => {
        setEnabledFeatures(new Set(data.enabled_features));
        setError(null);
      })
      .catch(err => {
        console.error('Failed to fetch features:', err);
        setError(err);
        // Fallback: assume all features enabled if fetch fails
        setEnabledFeatures(new Set());
      })
      .finally(() => setLoading(false));
  }, [workspaceId]);

  const isFeatureEnabled = (featureName) => {
    return enabledFeatures.has(featureName);
  };

  return { isFeatureEnabled, enabledFeatures, loading, error };
};
```

Behavior:
- Fetches on mount and workspace change
- If fetch fails, assumes all features enabled (fail-open)
- Returns helper function `isFeatureEnabled('listings')`

#### F2: Update API Client
**File**: `frontend/src/api/client.js` (MODIFY)

Add functions:
```javascript
export const getFeatures = () => api.get('/api/features');

export const getWorkspaceFeaturesEnabled = () =>
  api.get('/api/features/workspace-enabled');

export const updateFeatureVisibility = (featureName, enabled) =>
  api.post(`/api/features/${featureName}/visibility`, { enabled });

export const getFeatureDataSummary = (featureName) =>
  api.get(`/api/features/${featureName}/data-summary`);
```

#### F3: Update App.jsx Navigation
**File**: `frontend/src/App.jsx` (MODIFY)

Import and use hook:
```javascript
import { useFeatureVisibility } from './hooks/useFeatureVisibility';

function App() {
  const { isFeatureEnabled, loading } = useFeatureVisibility();

  if (loading) return <LoadingSpinner />;

  return (
    <nav>
      {isFeatureEnabled('campaigns') && (
        <NavLink to="/campaigns">Campaigns</NavLink>
      )}
      {isFeatureEnabled('contacts') && (
        <NavLink to="/contacts">Contacts</NavLink>
      )}
      {isFeatureEnabled('listings') && (
        <NavLink to="/listings">Listings</NavLink>
      )}
      {/* Other nav items... */}
    </nav>

    <Routes>
      {isFeatureEnabled('campaigns') && (
        <Route path="/campaigns" element={<CampaignList />} />
      )}
      {isFeatureEnabled('contacts') && (
        <Route path="/contacts" element={<ContactList />} />
      )}
      {isFeatureEnabled('listings') && (
        <Route path="/listings" element={<ListingsPage />} />
      )}
      {/* Other routes... */}
    </Routes>
  );
}
```

Effect:
- Disabled features don't appear in navigation
- Disabled features don't have routes (accessing URL directly shows 404)
- Users only see allowed features

#### F4: Create FeatureVisibilityToggle Component
**File**: `frontend/src/components/FeatureVisibilityToggle.jsx` (NEW)

```javascript
import React, { useState } from 'react';
import * as api from '../api/client';

export const FeatureVisibilityToggle = ({ feature, onToggleComplete }) => {
  const [enabled, setEnabled] = useState(feature.enabled);
  const [loading, setLoading] = useState(false);
  const [showWarning, setShowWarning] = useState(false);
  const [dataCounts, setDataCounts] = useState(null);

  const handleToggle = async (newEnabled) => {
    if (!newEnabled && !showWarning) {
      // Show warning before disabling
      setLoading(true);
      try {
        const counts = await api.getFeatureDataSummary(feature.name);
        setDataCounts(counts);
        setShowWarning(true);
      } finally {
        setLoading(false);
      }
      return;
    }

    setLoading(true);
    try {
      await api.updateFeatureVisibility(feature.name, newEnabled);
      setEnabled(newEnabled);
      setShowWarning(false);
      onToggleComplete?.();
    } catch (error) {
      console.error('Failed to update feature visibility:', error);
      // Error handling
    } finally {
      setLoading(false);
    }
  };

  const totalRecords = dataCounts
    ? Object.values(dataCounts).reduce((a, b) => a + b, 0)
    : 0;

  return (
    <div className="feature-toggle">
      <label>
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => handleToggle(e.target.checked)}
          disabled={loading}
        />
        <span className="feature-name">{feature.display_name}</span>
      </label>
      <p className="feature-description">{feature.description}</p>

      {showWarning && dataCounts && (
        <div className="warning-box">
          <p>
            ⚠️ <strong>Warning:</strong> This feature contains{' '}
            <strong>{totalRecords} records</strong>:
          </p>
          <ul>
            {Object.entries(dataCounts).map(([table, count]) => (
              count > 0 && <li key={table}>{count} {table}</li>
            ))}
          </ul>
          <p>
            These records will be hidden but preserved in the database. They will
            become accessible again if you re-enable this feature.
          </p>
          <button onClick={() => handleToggle(false)} disabled={loading}>
            Confirm Disable
          </button>
          <button onClick={() => setShowWarning(false)} disabled={loading}>
            Cancel
          </button>
        </div>
      )}
    </div>
  );
};
```

Features:
- Checkbox to toggle feature
- Shows feature name and description
- On disable: Fetches data counts and shows warning
- Warns user about records that will be hidden
- Requires explicit confirmation to disable with data

#### F5: Add Feature Visibility Section to Settings
**File**: `frontend/src/pages/Settings.jsx` (MODIFY)

Add new section:
```javascript
const [allFeatures, setAllFeatures] = useState([]);
const [workspaceFeatures, setWorkspaceFeatures] = useState({});

useEffect(() => {
  // Fetch all available features
  api.getFeatures()
    .then(data => {
      // Format features with enabled status
      const withStatus = Object.values(data.features).map(feature => ({
        ...feature,
        enabled: workspaceFeatures[feature.name] !== false,
      }));
      setAllFeatures(withStatus);
    });
}, [workspaceFeatures]);

// In JSX, add tab or section:
<div className="settings-section">
  <h2>Feature Visibility</h2>
  <p>Control which features are visible in this workspace.</p>
  <div className="features-grid">
    {allFeatures.map(feature => (
      <FeatureVisibilityToggle
        key={feature.name}
        feature={feature}
        onToggleComplete={() => {
          // Refresh workspace features
          api.getWorkspaceFeaturesEnabled()
            .then(data => setWorkspaceFeatures(data.feature_info));
        }}
      />
    ))}
  </div>
</div>
```

#### F6: Update Workspace Selector (if applicable)
**File**: `frontend/src/components/WorkspaceSelector.jsx` (MODIFY)

When workspace changes, trigger feature refresh:
```javascript
const handleWorkspaceChange = (newWorkspaceId) => {
  // ... existing logic
  // This will trigger useFeatureVisibility to refetch
  dispatch(workspaceChanged(newWorkspaceId));
};
```

### Phase 3: Integration & Testing

#### T1: Backend Testing
- Unit test: `is_feature_enabled()` with different workspace_id values
- Unit test: `set_feature_visibility()` creates/updates WorkspaceSettings entry
- API test: GET `/api/features` returns all features
- API test: POST `/api/features/listings/visibility` with admin user succeeds
- API test: POST `/api/features/listings/visibility` with non-admin user fails (403)
- API test: GET `/api/features/workspace-enabled` returns only enabled features

#### T2: Frontend Testing
- Hook test: `useFeatureVisibility` fetches on mount
- Hook test: `useFeatureVisibility` refetches on workspace change
- Component test: FeatureVisibilityToggle renders and toggles
- Integration test: Disable listings feature, verify NavLink disappears and route removed
- Integration test: Re-enable feature, verify NavLink/route restored

#### T3: Manual Testing (User Acceptance)
1. Create/access workspace "construction"
2. Navigate to Settings → Feature Visibility
3. Verify all features shown with checkmarks
4. Disable "Listings" feature
5. Verify "Listings" tab disappears from navigation
6. Try accessing `/listings` directly → should show 404 or redirect
7. Re-enable "Listings"
8. Verify "Listings" tab reappears
9. Verify previously created monitored sites/listings still exist
10. Switch to another workspace ("business outreach")
11. Verify "Listings" is enabled by default
12. Test data counts warning when disabling feature with data

---

## Critical Implementation Notes

### User/Role System
**TODO**: The `require_workspace_admin()` function needs implementation. Determine:
- How are users currently identified? (Flask-Login, JWT, session?)
- How are workspace admins determined? (User field? Separate table?)
- If no role system exists: Is workspace creator always admin? Should first user to set up workspace be admin?

### Feature Registry
The FEATURES dict must include ALL currently available features. Audit the codebase for:
- All blueprints registered in `app/__init__.py`
- All routes registered in `app/routes/`
- All pages/components in `frontend/src/pages/`

### Data Table Mapping
For each feature, accurately list which database tables it owns/manages:
- Listings → `monitored_site`, `listing`, `deal_criteria`
- Campaigns → `campaign`, `campaign_step`, `recipient`, `email_log`, `step_recipient`
- Contacts → `contact`, `contact_tags`, `tag`
- Etc.

This is critical for:
- Data count warnings in UI
- Future data archival/cleanup features
- Understanding data cascades

### Backward Compatibility
- Existing workspaces: All features enabled (WorkspaceSettings key doesn't exist = default enabled)
- New workspaces: All features enabled by default
- No migration required for existing data

---

## Files to Create/Modify

### NEW FILES:
- `backend/app/services/feature_service.py` - Feature registry and utilities
- `backend/app/routes/features.py` - Feature API endpoints
- `frontend/src/hooks/useFeatureVisibility.js` - Feature visibility hook
- `frontend/src/components/FeatureVisibilityToggle.jsx` - Toggle component

### MODIFY:
- `backend/app/__init__.py` - Register features blueprint
- `frontend/src/api/client.js` - Add feature API functions
- `frontend/src/App.jsx` - Conditionally render nav/routes
- `frontend/src/pages/Settings.jsx` - Add Feature Visibility section

---

## Rollout Plan

1. **Week 1**: Implement backend (B1-B4)
   - Create feature service
   - Create API endpoints
   - Deploy (no user-facing changes yet)
   - Test API endpoints

2. **Week 2**: Implement frontend (F1-F6)
   - Create hook, components, update App.jsx
   - Test navigation changes
   - Deploy

3. **Week 3**: User acceptance testing and refinement
   - Test with multiple workspaces
   - Gather feedback
   - Fix any issues

---

## Success Criteria

✅ User can navigate to Settings → Feature Visibility
✅ User can toggle feature visibility for their workspace
✅ Disabled features disappear from navigation immediately
✅ Disabled features can't be accessed via direct URL
✅ Data is preserved when feature is disabled
✅ Re-enabling a feature restores access to all historical data
✅ Different workspaces can have different feature configurations
✅ Only workspace admins can change feature settings
✅ New features added automatically appear (and are enabled by default)

---

## Future Enhancements (Out of Scope)

1. **Feature Dependencies**: Don't allow disabling Campaign if Follow-ups depend on it
2. **Data Archive**: Endpoint to export feature data before permanent deletion
3. **Feature Descriptions**: Detailed explanations of what each feature does
4. **Usage Analytics**: Track which features are most used per workspace
5. **Trial Features**: Mark features as "beta" or "experimental"
6. **Billing Integration**: Different tiers with different feature sets
