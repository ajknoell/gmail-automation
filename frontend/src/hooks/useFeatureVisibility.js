import { useState, useEffect } from 'react';
import { getEnabledFeatures } from '../api/client';

/**
 * Hook to manage feature visibility for the current workspace.
 * Fetches enabled features on mount and refetches on workspace change.
 */
export function useFeatureVisibility() {
  const [enabledFeatures, setEnabledFeatures] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadEnabledFeatures = async () => {
    setLoading(true);
    try {
      const res = await getEnabledFeatures();
      setEnabledFeatures(res.data.enabled_features || []);
    } catch (error) {
      console.error('Failed to load enabled features:', error);
      // Fail-open: treat all features as enabled if fetch fails
      setEnabledFeatures([
        'insights',
        'replies',
        'quick_send',
        'campaigns',
        'follow_ups',
        'templates',
        'contacts',
        'listings',
        'cold_calls',
      ]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadEnabledFeatures();

    // Re-fetch when workspace changes
    const handleWorkspaceChange = () => {
      loadEnabledFeatures();
    };
    window.addEventListener('workspace-changed', handleWorkspaceChange);
    return () => window.removeEventListener('workspace-changed', handleWorkspaceChange);
  }, []);

  const isFeatureEnabled = (featureName) => {
    return enabledFeatures.includes(featureName);
  };

  return {
    isFeatureEnabled,
    enabledFeatures,
    loading,
    reloadFeatures: loadEnabledFeatures,
  };
}
