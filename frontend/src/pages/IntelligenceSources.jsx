import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  getSignalSources, createSignalSource, updateSignalSource,
  getTriggerConfig, signalCollectNow,
} from '../api/client';
import { useToast } from '../components/Toast';
import { SOURCE_DESCRIPTIONS, timeAgo } from '../utils/intelligence';

// All source types that can be managed via SignalSource model
const SIGNAL_SOURCE_TYPES = ['news', 'job_posting', 'funding', 'tech_change'];

function IntelligenceSources() {
  const showToast = useToast();
  const [sources, setSources] = useState([]);
  const [triggerConfig, setTriggerConfig] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [sourcesRes, configRes] = await Promise.all([
        getSignalSources(),
        getTriggerConfig().catch(() => ({ data: null })),
      ]);
      setSources(sourcesRes.data.sources || []);
      setTriggerConfig(configRes.data);
    } catch (err) {
      console.error('Sources load error:', err);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadAll();
    const handleWsChange = () => loadAll();
    window.addEventListener('workspace-changed', handleWsChange);
    return () => window.removeEventListener('workspace-changed', handleWsChange);
  }, [loadAll]);

  const handleEnable = async (sourceType) => {
    try {
      const info = SOURCE_DESCRIPTIONS[sourceType] || {};
      await createSignalSource({
        source_type: sourceType,
        name: info.name || sourceType.replace('_', ' '),
      });
      showToast(`${info.name || sourceType} enabled`, 'success');
      loadAll();
    } catch (err) {
      showToast('Failed to enable source: ' + (err.response?.data?.error || err.message), 'error');
    }
  };

  const handleToggle = async (source) => {
    try {
      await updateSignalSource(source.id, { is_active: !source.is_active });
      showToast(`${source.name} ${source.is_active ? 'disabled' : 'enabled'}`, 'info');
      loadAll();
    } catch (err) {
      showToast('Failed to update source: ' + (err.response?.data?.error || err.message), 'error');
    }
  };

  const handleCollectNow = async () => {
    try {
      await signalCollectNow();
      showToast('Collecting signals in background \u2014 new results will appear shortly.', 'info');
    } catch (err) {
      showToast('Collection failed: ' + (err.response?.data?.error || err.message), 'error');
    }
  };

  // Split sources into active and available
  const activeSourceTypes = new Set(sources.map(s => s.source_type));
  const activeSources = sources.filter(s => s.is_active);
  const disabledSources = sources.filter(s => !s.is_active);
  const availableTypes = SIGNAL_SOURCE_TYPES.filter(t => !activeSourceTypes.has(t));

  if (loading) {
    return (
      <div className="page">
        <div className="page-header"><h1>Intelligence Sources</h1></div>
        <p style={{ color: 'var(--text-light)' }}>Loading...</p>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>Intelligence Sources</h1>
        <button className="btn btn-primary" onClick={handleCollectNow}>
          Collect Now
        </button>
      </div>

      <p style={{ color: 'var(--text-light)', fontSize: '0.875rem', marginBottom: '1.5rem' }}>
        Configure what Veloro monitors across your prospect companies. Each source runs automatically on a schedule.
      </p>

      {/* Website Monitoring (always-on) */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem' }}>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.375rem' }}>
              <span style={{ fontSize: '1.25rem' }}>{'\u{1F310}'}</span>
              <strong style={{ fontSize: '1rem' }}>Website Monitoring</strong>
              <span style={{
                fontSize: '0.7rem', padding: '0.125rem 0.5rem', borderRadius: '9999px',
                background: '#D1FAE5', color: '#065F46', fontWeight: 600,
              }}>always on</span>
            </div>
            <p style={{ fontSize: '0.875rem', color: 'var(--text-light)', marginBottom: '0.5rem', lineHeight: 1.5 }}>
              Automatically checks your contacts' websites for SSL certificate issues, downtime,
              content changes, and outdated copyright years. Each issue creates a natural outreach opportunity.
            </p>
            <div style={{ fontSize: '0.8125rem', color: '#9CA3AF' }}>
              Runs every 24 hours for contacts with websites
              {triggerConfig && !triggerConfig.enabled && (
                <span style={{ color: SEVERITY_COLORS?.important || '#F59E0B', marginLeft: '0.5rem' }}>
                  (currently paused in settings)
                </span>
              )}
            </div>
          </div>
          <Link to="/intelligence/triggers" className="btn btn-sm btn-secondary" style={{ flexShrink: 0 }}>
            View Triggers
          </Link>
        </div>
      </div>

      {/* Active Signal Sources */}
      {activeSources.length > 0 && (
        <>
          <h2 style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-light)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.75rem' }}>
            Active Sources
          </h2>
          <div style={{ display: 'grid', gap: '0.75rem', marginBottom: '1.5rem' }}>
            {activeSources.map(source => {
              const info = SOURCE_DESCRIPTIONS[source.source_type] || {};
              return (
                <div key={source.id} className="card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem' }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.375rem' }}>
                        <span style={{ fontSize: '1.25rem' }}>{info.icon || '\u{1F4E1}'}</span>
                        <strong style={{ fontSize: '0.9375rem' }}>{source.name || info.name}</strong>
                      </div>
                      <p style={{ fontSize: '0.875rem', color: 'var(--text-light)', marginBottom: '0.5rem', lineHeight: 1.5 }}>
                        {info.description}
                      </p>
                      <div style={{ fontSize: '0.8125rem', color: '#9CA3AF' }}>
                        Every {source.check_interval_hours}h
                        {source.last_checked_at && (
                          <> &middot; Last checked {timeAgo(source.last_checked_at)}</>
                        )}
                        {source.last_error && (
                          <span style={{ color: '#EF4444' }}> &middot; Error: {source.last_error.substring(0, 80)}</span>
                        )}
                      </div>
                    </div>
                    <button className="btn btn-sm btn-secondary" onClick={() => handleToggle(source)}
                      style={{ flexShrink: 0 }}>
                      Disable
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* Disabled Sources */}
      {disabledSources.length > 0 && (
        <>
          <h2 style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-light)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.75rem' }}>
            Disabled Sources
          </h2>
          <div style={{ display: 'grid', gap: '0.75rem', marginBottom: '1.5rem' }}>
            {disabledSources.map(source => {
              const info = SOURCE_DESCRIPTIONS[source.source_type] || {};
              return (
                <div key={source.id} className="card" style={{ opacity: 0.7 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem' }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                        <span style={{ fontSize: '1.25rem' }}>{info.icon || '\u{1F4E1}'}</span>
                        <strong style={{ fontSize: '0.9375rem' }}>{source.name || info.name}</strong>
                      </div>
                      <p style={{ fontSize: '0.875rem', color: 'var(--text-light)', lineHeight: 1.5 }}>
                        {info.description}
                      </p>
                    </div>
                    <button className="btn btn-sm btn-primary" onClick={() => handleToggle(source)}
                      style={{ flexShrink: 0 }}>
                      Enable
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* Available (not yet created) Sources */}
      {availableTypes.length > 0 && (
        <>
          <h2 style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-light)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.75rem' }}>
            Available Sources
          </h2>
          <div style={{ display: 'grid', gap: '0.75rem', marginBottom: '1.5rem' }}>
            {availableTypes.map(type => {
              const info = SOURCE_DESCRIPTIONS[type] || {};
              return (
                <div key={type} className="card" style={{
                  borderStyle: 'dashed', borderColor: 'var(--border)', opacity: 0.85,
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem' }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                        <span style={{ fontSize: '1.25rem' }}>{info.icon || '\u{1F4E1}'}</span>
                        <strong style={{ fontSize: '0.9375rem' }}>{info.name || type}</strong>
                      </div>
                      <p style={{ fontSize: '0.875rem', color: 'var(--text-light)', lineHeight: 1.5 }}>
                        {info.description}
                      </p>
                    </div>
                    <button className="btn btn-sm btn-primary" onClick={() => handleEnable(type)}
                      style={{ flexShrink: 0 }}>
                      Enable
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* Footer note */}
      <p style={{ fontSize: '0.8125rem', color: '#9CA3AF', lineHeight: 1.5 }}>
        Website monitoring is always active for contacts with websites.
        Signal sources (news, job postings) require a Tavily API key configured in{' '}
        <Link to="/settings" style={{ color: 'var(--primary)' }}>Settings</Link>.
      </p>
    </div>
  );
}

export default IntelligenceSources;
