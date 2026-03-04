import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  getSignals, getTriggers, getSignalStats, getTriggerStats,
  getOpportunityFeed, getSignalSources,
  createSignalOutreach, createTriggerOutreach,
  dismissSignal, dismissTrigger,
  signalCollectNow, triggerCheckNow,
} from '../api/client';
import { useToast } from '../components/Toast';
import {
  SOURCE_ICONS, SOURCE_LABELS, SEVERITY_COLORS,
  TRIGGER_LABELS, TRIGGER_ICONS,
  isWebsiteTrigger, getItemTitle, getItemIcon,
  getItemSourceLabel, getHumanSummary, timeAgo,
} from '../utils/intelligence';

function ScoreBadge({ score, label }) {
  if (score == null) return null;
  const pct = Math.round(score * 100);
  let bg = '#F3F4F6';
  let color = '#374151';
  if (score >= 0.7) { bg = '#D1FAE5'; color = '#065F46'; }
  else if (score >= 0.4) { bg = '#FEF3C7'; color = '#92400E'; }
  return (
    <span style={{
      fontSize: '0.75rem', padding: '0.125rem 0.5rem', borderRadius: '9999px',
      background: bg, color, fontWeight: 600,
    }}>
      {pct}% {label}
    </span>
  );
}

function Intelligence() {
  const showToast = useToast();
  const [tab, setTab] = useState('feed');

  // Feed state
  const [feedItems, setFeedItems] = useState([]);
  const [signalStats, setSignalStats] = useState({});
  const [triggerStats, setTriggerStats] = useState({});
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(true);

  // Opportunities state
  const [opportunities, setOpportunities] = useState([]);
  const [oppTotal, setOppTotal] = useState(0);
  const [oppPage, setOppPage] = useState(1);
  const [oppLoading, setOppLoading] = useState(false);

  // Action state
  const [generatingId, setGeneratingId] = useState(null);
  const [generatingType, setGeneratingType] = useState(null); // 'signal' or 'trigger'
  const [outreachPreview, setOutreachPreview] = useState(null);
  const [outreachSourceItem, setOutreachSourceItem] = useState(null);
  const [collecting, setCollecting] = useState(false);
  const [checking, setChecking] = useState(false);

  // Filter
  const [filterSource, setFilterSource] = useState('');

  const loadFeed = useCallback(async () => {
    setLoading(true);
    try {
      const signalParams = {};
      const triggerParams = {};
      if (filterSource) {
        if (filterSource === 'website') {
          triggerParams.type = ''; // get all trigger types
        } else {
          signalParams.source_type = filterSource;
        }
      }

      const requests = [getSignalStats(), getTriggerStats(), getSignalSources()];
      // Only fetch relevant data based on filter
      if (!filterSource || filterSource !== 'website') {
        requests.push(getSignals(signalParams));
      }
      if (!filterSource || filterSource === 'website' || filterSource === '') {
        requests.push(getTriggers(triggerParams));
      }

      const results = await Promise.all(requests);

      setSignalStats(results[0].data);
      setTriggerStats(results[1].data);
      setSources(results[2].data.sources || []);

      // Merge signals and triggers into a unified feed
      const signals = [];
      const triggers = [];
      let idx = 3;

      if (!filterSource || filterSource !== 'website') {
        signals.push(...(results[idx]?.data?.signals || []));
        idx++;
      }
      if (!filterSource || filterSource === 'website' || filterSource === '') {
        triggers.push(...(results[idx]?.data?.triggers || []));
      }

      // Normalize triggers to look similar to signals for display
      const normalizedTriggers = triggers.map(t => ({
        ...t,
        // Keep trigger_type to identify as trigger
        detected_at: t.detected_at || t.created_at,
        contact_name: t.contact_name,
        contact_email: t.contact_email,
        contact_company: t.contact_company,
        source_type: 'website',
      }));

      // Merge and sort by detected_at descending
      const merged = [...signals, ...normalizedTriggers].sort((a, b) => {
        const dateA = new Date(a.detected_at || a.created_at || 0);
        const dateB = new Date(b.detected_at || b.created_at || 0);
        return dateB - dateA;
      });

      setFeedItems(merged);
    } catch (err) {
      console.error('Intelligence load error:', err);
    }
    setLoading(false);
  }, [filterSource]);

  const loadOpportunities = useCallback(async () => {
    setOppLoading(true);
    try {
      const res = await getOpportunityFeed({ page: oppPage, per_page: 20 });
      setOpportunities(res.data.opportunities || []);
      setOppTotal(res.data.total || 0);
    } catch (err) {
      console.error('Opportunities load error:', err);
    }
    setOppLoading(false);
  }, [oppPage]);

  useEffect(() => {
    loadFeed();
    if (tab === 'opportunities') loadOpportunities();
    const handleWsChange = () => { loadFeed(); if (tab === 'opportunities') loadOpportunities(); };
    window.addEventListener('workspace-changed', handleWsChange);
    return () => window.removeEventListener('workspace-changed', handleWsChange);
  }, [loadFeed, loadOpportunities, tab]);

  useEffect(() => {
    if (tab === 'opportunities') loadOpportunities();
  }, [tab, loadOpportunities]);

  // ─── Actions ─────────────────────────────────────────────────
  const handleCreateOutreach = async (item) => {
    const isTrigger = isWebsiteTrigger(item);
    setGeneratingId(item.id);
    setGeneratingType(isTrigger ? 'trigger' : 'signal');
    try {
      const res = isTrigger
        ? await createTriggerOutreach(item.id)
        : await createSignalOutreach(item.id);
      setOutreachSourceItem(item);
      setOutreachPreview(res.data);
      loadFeed();
    } catch (err) {
      showToast('Generation failed: ' + (err.response?.data?.error || err.message), 'error');
    }
    setGeneratingId(null);
    setGeneratingType(null);
  };

  const handleDismiss = async (item) => {
    try {
      if (isWebsiteTrigger(item)) {
        await dismissTrigger(item.id);
      } else {
        await dismissSignal(item.id);
      }
      loadFeed();
    } catch (err) {
      showToast('Dismiss failed: ' + (err.response?.data?.error || err.message), 'error');
    }
  };

  const handleCollectNow = async () => {
    setCollecting(true);
    try {
      await signalCollectNow();
      showToast('Collecting signals in background \u2014 new results will appear shortly.', 'info');
      setTimeout(loadFeed, 5000);
    } catch (err) {
      showToast('Collection failed: ' + (err.response?.data?.error || err.message), 'error');
    }
    setCollecting(false);
  };

  const handleCheckNow = async () => {
    setChecking(true);
    try {
      await triggerCheckNow();
      showToast('Scanning contact websites \u2014 this may take a minute.', 'info');
      setTimeout(loadFeed, 5000);
    } catch (err) {
      showToast('Check failed: ' + (err.response?.data?.error || err.message), 'error');
    }
    setChecking(false);
  };

  const handleCopyOutreach = () => {
    if (!outreachPreview) return;
    const subject = outreachPreview.outreach_subject || outreachPreview.subject || '';
    const body = outreachPreview.outreach_body || outreachPreview.body || '';
    navigator.clipboard.writeText(`Subject: ${subject}\n\n${body}`);
    showToast('Copied to clipboard', 'success');
  };

  const handleRegenerateOutreach = async () => {
    if (!outreachSourceItem) return;
    setOutreachPreview(null);
    await handleCreateOutreach(outreachSourceItem);
  };

  const handleOppOutreach = async (signalId) => {
    setGeneratingId(signalId);
    try {
      await createSignalOutreach(signalId);
      loadOpportunities();
    } catch (err) {
      showToast('Generation failed: ' + (err.response?.data?.error || err.message), 'error');
    }
    setGeneratingId(null);
  };

  // ─── Stats ───────────────────────────────────────────────────
  const totalSignals = (signalStats.total || 0) + (triggerStats.total || 0);
  const totalPending = (signalStats.pending || 0) + (triggerStats.pending || 0);
  const totalActioned = (signalStats.actioned || 0) + (triggerStats.actioned || 0);
  const activeSources = sources.filter(s => s.is_active).length + 1; // +1 for website monitoring (always on)
  const isEmpty = feedItems.length === 0 && !loading;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Intelligence</h1>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-secondary" onClick={handleCollectNow} disabled={collecting}>
            {collecting ? 'Collecting...' : 'Collect Signals'}
          </button>
          <button className="btn btn-secondary" onClick={handleCheckNow} disabled={checking}>
            {checking ? 'Scanning...' : 'Scan Websites'}
          </button>
        </div>
      </div>

      <p style={{ color: 'var(--text-light)', fontSize: '0.875rem', marginBottom: '1rem' }}>
        AI-powered monitoring of your prospects \u2014 every signal is a reason to reach out.
      </p>

      {/* Stats */}
      {!isEmpty && (
        <div className="stats-row">
          <div className="stat-card">
            <div className="stat-value">{totalSignals}</div>
            <div className="stat-label">Total Active</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{totalPending}</div>
            <div className="stat-label">Pending</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{totalActioned}</div>
            <div className="stat-label">Actioned</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{activeSources}</div>
            <div className="stat-label">Sources</div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div style={{
        display: 'flex', gap: '0', borderBottom: '1px solid var(--border)',
        marginBottom: '1rem',
      }}>
        {['feed', 'opportunities'].map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: '0.625rem 1.25rem',
              fontSize: '0.875rem',
              fontWeight: tab === t ? 600 : 400,
              color: tab === t ? 'var(--primary)' : 'var(--text-light)',
              background: 'none',
              border: 'none',
              borderBottom: tab === t ? '2px solid var(--primary)' : '2px solid transparent',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            {t === 'feed' ? 'Feed' : 'Top Opportunities'}
          </button>
        ))}
      </div>

      {/* ─── Feed Tab ─────────────────────────────────────────── */}
      {tab === 'feed' && (
        <>
          {/* Filter */}
          <div style={{ marginBottom: '1rem' }}>
            <select value={filterSource} onChange={e => setFilterSource(e.target.value)}
              className="input" style={{ maxWidth: '200px' }}>
              <option value="">All Sources</option>
              <option value="website">Website Monitor</option>
              {Object.entries(SOURCE_LABELS).filter(([k]) => k !== 'website').map(([key, label]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
          </div>

          {loading ? (
            <p style={{ color: 'var(--text-light)' }}>Loading...</p>
          ) : isEmpty ? (
            /* ─── Empty State ─────────────────────────────────── */
            <div className="card" style={{ padding: '2.5rem 2rem' }}>
              <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
                <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>{'\u{1F4E1}'}</div>
                <h2 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '0.5rem' }}>Your AI Radar</h2>
                <p style={{ color: 'var(--text-light)', fontSize: '0.9rem', maxWidth: '500px', margin: '0 auto', lineHeight: 1.6 }}>
                  Veloro watches your prospects around the clock and alerts you the moment
                  something happens &mdash; so you always reach out at the perfect time.
                </p>
              </div>

              {/* Feature cards */}
              <div style={{
                display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                gap: '1rem', marginBottom: '2rem',
              }}>
                {[
                  { icon: '\u{1F310}', title: 'Website Monitoring', desc: 'SSL issues, downtime, content changes, and site neglect' },
                  { icon: '\u{1F4F0}', title: 'News & Funding', desc: 'Funding rounds, leadership changes, expansions' },
                  { icon: '\u{1F4BC}', title: 'Hiring Activity', desc: 'Job posts that signal growth or emerging needs' },
                ].map(f => (
                  <div key={f.title} style={{
                    padding: '1.25rem', borderRadius: '0.75rem', background: 'var(--bg)',
                    border: '1px solid var(--border)', textAlign: 'center',
                  }}>
                    <div style={{ fontSize: '1.75rem', marginBottom: '0.5rem' }}>{f.icon}</div>
                    <div style={{ fontWeight: 600, fontSize: '0.875rem', marginBottom: '0.375rem' }}>{f.title}</div>
                    <div style={{ fontSize: '0.8125rem', color: 'var(--text-light)', lineHeight: 1.4 }}>{f.desc}</div>
                  </div>
                ))}
              </div>

              {/* How it works */}
              <div style={{ maxWidth: '420px', margin: '0 auto' }}>
                <h3 style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: '0.75rem' }}>How it works</h3>
                {[
                  { num: '1', text: 'Add contacts with company names or websites' },
                  { num: '2', text: 'Enable monitoring sources' },
                  { num: '3', text: 'AI surfaces opportunities and writes your outreach' },
                ].map(step => (
                  <div key={step.num} style={{
                    display: 'flex', alignItems: 'center', gap: '0.75rem',
                    marginBottom: '0.5rem',
                  }}>
                    <span style={{
                      width: '1.75rem', height: '1.75rem', borderRadius: '50%',
                      background: 'var(--primary)', color: 'white', display: 'flex',
                      alignItems: 'center', justifyContent: 'center',
                      fontSize: '0.75rem', fontWeight: 700, flexShrink: 0,
                    }}>{step.num}</span>
                    <span style={{ fontSize: '0.875rem' }}>{step.text}</span>
                  </div>
                ))}
              </div>

              <div style={{ textAlign: 'center', marginTop: '1.5rem' }}>
                <Link to="/intelligence/sources" className="btn btn-primary">
                  Set Up Sources
                </Link>
              </div>
            </div>
          ) : (
            /* ─── Feed Items ──────────────────────────────────── */
            <div style={{ display: 'grid', gap: '0.625rem' }}>
              {feedItems.map(item => {
                const isTrigger = isWebsiteTrigger(item);
                const severity = item.severity || 'info';
                const isGenerating = generatingId === item.id && generatingType === (isTrigger ? 'trigger' : 'signal');

                return (
                  <div key={`${isTrigger ? 't' : 's'}-${item.id}`} className="card" style={{
                    padding: '1rem 1.25rem',
                    borderLeft: `3px solid ${SEVERITY_COLORS[severity] || '#6B7280'}`,
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '0.75rem' }}>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        {/* Header row */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.375rem', flexWrap: 'wrap' }}>
                          <span style={{ fontSize: '1.1em' }}>{getItemIcon(item)}</span>
                          <strong style={{ fontSize: '0.9rem' }}>{getItemTitle(item)}</strong>
                          {!isTrigger && item.intent_score != null && (
                            <ScoreBadge score={item.intent_score} label="intent" />
                          )}
                          {severity === 'critical' && (
                            <span style={{
                              fontSize: '0.7rem', padding: '0.0625rem 0.375rem', borderRadius: '9999px',
                              background: SEVERITY_COLORS.critical, color: 'white', fontWeight: 600,
                            }}>urgent</span>
                          )}
                        </div>

                        {/* Contact */}
                        <div style={{ fontSize: '0.875rem', marginBottom: '0.375rem' }}>
                          <strong>{item.contact_name || item.contact_email}</strong>
                          {item.contact_company && (
                            <span style={{ color: 'var(--text-light)' }}> &middot; {item.contact_company}</span>
                          )}
                        </div>

                        {/* Human-readable summary */}
                        <div style={{ fontSize: '0.8125rem', color: '#374151', lineHeight: 1.5, marginBottom: '0.375rem' }}>
                          {getHumanSummary(item)}
                        </div>

                        {/* Footer metadata */}
                        <div style={{ fontSize: '0.75rem', color: '#9CA3AF', display: 'flex', gap: '0.375rem', alignItems: 'center', flexWrap: 'wrap' }}>
                          <span>{timeAgo(item.detected_at || item.created_at)}</span>
                          <span>&middot;</span>
                          <span>via {getItemSourceLabel(item)}</span>
                          {item.source_url && (
                            <>
                              <span>&middot;</span>
                              <a href={item.source_url} target="_blank" rel="noopener noreferrer"
                                style={{ color: 'var(--primary)' }}>Source</a>
                            </>
                          )}
                        </div>
                      </div>

                      {/* Actions */}
                      <div style={{ display: 'flex', gap: '0.5rem', flexShrink: 0, alignItems: 'flex-start' }}>
                        {!item.actioned && (
                          <button className="btn btn-primary btn-sm" onClick={() => handleCreateOutreach(item)}
                            disabled={isGenerating}>
                            {isGenerating ? 'Generating...' : '\u2728 Create Outreach'}
                          </button>
                        )}
                        {item.actioned && (item.outreach_subject || item.outreach_body) && (
                          <button className="btn btn-sm btn-secondary" onClick={() => {
                            setOutreachSourceItem(item);
                            setOutreachPreview(item);
                          }}>
                            View Email
                          </button>
                        )}
                        <button className="btn btn-sm" onClick={() => handleDismiss(item)}
                          style={{ color: 'var(--text-light)' }}>
                          Dismiss
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {/* ─── Opportunities Tab ────────────────────────────────── */}
      {tab === 'opportunities' && (
        <>
          <p style={{ color: 'var(--text-light)', fontSize: '0.875rem', marginBottom: '1rem' }}>
            Contacts ranked by signal strength and relevance to your business profile.
            {oppTotal > 0 && <span style={{ marginLeft: '0.5rem' }}>{oppTotal} opportunit{oppTotal === 1 ? 'y' : 'ies'}</span>}
          </p>

          {oppLoading ? (
            <p style={{ color: 'var(--text-light)' }}>Loading...</p>
          ) : opportunities.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: '2.5rem 1.5rem', color: 'var(--text-light)' }}>
              <div style={{ fontSize: '2rem', marginBottom: '0.75rem', opacity: 0.5 }}>{'\u{1F4E1}'}</div>
              <p style={{ fontWeight: 500, marginBottom: '0.375rem' }}>No opportunities yet</p>
              <p style={{ fontSize: '0.875rem' }}>
                Set up your <Link to="/business-profile" style={{ color: 'var(--primary)' }}>Business Profile</Link> and
                enable <Link to="/intelligence/sources" style={{ color: 'var(--primary)' }}>Sources</Link> to start seeing ranked opportunities.
              </p>
            </div>
          ) : (
            <div style={{ display: 'grid', gap: '0.75rem' }}>
              {opportunities.map(opp => (
                <div key={opp.contact.id} className="card">
                  {/* Header */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem', gap: '0.75rem' }}>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.375rem', flexWrap: 'wrap' }}>
                        <Link to={`/contacts/${opp.contact.id}`} style={{
                          fontSize: '1rem', fontWeight: 600, color: 'var(--text)', textDecoration: 'none',
                        }}>
                          {opp.contact.name || opp.contact.email}
                        </Link>
                        {opp.contact.company && (
                          <span style={{ color: 'var(--text-light)', fontSize: '0.875rem' }}>{opp.contact.company}</span>
                        )}
                      </div>
                      <div style={{ display: 'flex', gap: '0.375rem', flexWrap: 'wrap' }}>
                        <ScoreBadge score={opp.max_intent_score} label="intent" />
                        <ScoreBadge score={opp.max_relevance_score} label="relevant" />
                        <span style={{
                          fontSize: '0.75rem', padding: '0.125rem 0.5rem', borderRadius: '9999px',
                          background: 'var(--bg)', color: 'var(--text-light)', border: '1px solid var(--border)',
                        }}>
                          {opp.signal_count} signal{opp.signal_count !== 1 ? 's' : ''}
                        </span>
                      </div>
                    </div>
                    <div style={{
                      fontSize: '1.25rem', fontWeight: 700, flexShrink: 0,
                      color: opp.combined_score >= 0.5 ? '#059669' : opp.combined_score >= 0.25 ? '#D97706' : 'var(--text-light)',
                      minWidth: '2.5rem', textAlign: 'right',
                    }}>
                      {Math.round(opp.combined_score * 100)}
                    </div>
                  </div>

                  {/* Signals */}
                  <div style={{ display: 'grid', gap: '0.375rem' }}>
                    {opp.top_signals.map(sig => (
                      <div key={sig.id} style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        padding: '0.5rem 0.75rem', borderRadius: '0.375rem', background: 'var(--bg)',
                        borderLeft: `3px solid ${SEVERITY_COLORS[sig.severity] || '#6B7280'}`,
                        gap: '0.5rem',
                      }}>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                            <span style={{ fontSize: '0.9em' }}>{SOURCE_ICONS[sig.source_type] || '\u{1F514}'}</span>
                            <span style={{ fontWeight: 500, fontSize: '0.8125rem' }}>{sig.title || sig.signal_type}</span>
                          </div>
                          {sig.summary && (
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-light)', marginTop: '0.125rem' }}>
                              {sig.summary.length > 120 ? sig.summary.slice(0, 120) + '...' : sig.summary}
                            </div>
                          )}
                        </div>
                        {!sig.actioned && (
                          <button className="btn btn-sm btn-primary" onClick={() => handleOppOutreach(sig.id)}
                            disabled={generatingId === sig.id} style={{ flexShrink: 0 }}>
                            {generatingId === sig.id ? '...' : 'Outreach'}
                          </button>
                        )}
                      </div>
                    ))}
                  </div>

                  {/* Footer */}
                  {opp.latest_signal_at && (
                    <div style={{ fontSize: '0.75rem', color: '#9CA3AF', marginTop: '0.625rem' }}>
                      Latest: {timeAgo(opp.latest_signal_at)}
                      {opp.contact.business_category && <> &middot; {opp.contact.business_category}</>}
                      {opp.contact.website && (
                        <> &middot; <a href={opp.contact.website.startsWith('http') ? opp.contact.website : `https://${opp.contact.website}`}
                          target="_blank" rel="noopener noreferrer" style={{ color: 'var(--primary)' }}>Website</a></>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Pagination */}
          {oppTotal > 20 && (
            <div style={{ display: 'flex', justifyContent: 'center', gap: '0.5rem', marginTop: '1.5rem', alignItems: 'center' }}>
              <button className="btn btn-sm btn-secondary" onClick={() => setOppPage(p => Math.max(1, p - 1))} disabled={oppPage <= 1}>
                Previous
              </button>
              <span style={{ padding: '0.25rem 0.75rem', color: 'var(--text-light)', fontSize: '0.8125rem' }}>
                Page {oppPage} of {Math.ceil(oppTotal / 20)}
              </span>
              <button className="btn btn-sm btn-secondary" onClick={() => setOppPage(p => p + 1)} disabled={oppPage >= Math.ceil(oppTotal / 20)}>
                Next
              </button>
            </div>
          )}
        </>
      )}

      {/* ─── Enhanced Outreach Preview Modal ──────────────────── */}
      {outreachPreview && (
        <div className="modal-overlay" onClick={() => { setOutreachPreview(null); setOutreachSourceItem(null); }}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: '600px' }}>
            <div className="modal-header">
              <div className="modal-title">Generated Outreach</div>
              <button className="modal-close" onClick={() => { setOutreachPreview(null); setOutreachSourceItem(null); }}>&times;</button>
            </div>
            <div className="modal-body">
              {/* Signal context */}
              {outreachSourceItem && (
                <div style={{
                  display: 'flex', alignItems: 'center', gap: '0.5rem',
                  padding: '0.625rem 0.75rem', borderRadius: '0.5rem',
                  background: 'rgba(79, 70, 229, 0.04)', border: '1px solid rgba(79, 70, 229, 0.12)',
                  marginBottom: '1rem', fontSize: '0.8125rem',
                }}>
                  <span>{getItemIcon(outreachSourceItem)}</span>
                  <span>
                    <strong>Based on:</strong> {getItemTitle(outreachSourceItem)}
                    {(outreachSourceItem.contact_name || outreachSourceItem.contact_company) && (
                      <span style={{ color: 'var(--text-light)' }}>
                        {' '}&middot; {outreachSourceItem.contact_name}{outreachSourceItem.contact_company ? ` at ${outreachSourceItem.contact_company}` : ''}
                      </span>
                    )}
                  </span>
                </div>
              )}

              <div style={{ marginBottom: '1rem' }}>
                <label className="label">Subject</label>
                <p style={{ fontSize: '0.9rem' }}>{outreachPreview.outreach_subject || outreachPreview.subject}</p>
              </div>
              <div>
                <label className="label">Body</label>
                <div style={{
                  whiteSpace: 'pre-wrap', background: 'var(--bg)', padding: '0.75rem',
                  borderRadius: '0.5rem', fontSize: '0.875rem', lineHeight: 1.6,
                  border: '1px solid var(--border)',
                }}>
                  {outreachPreview.outreach_body || outreachPreview.body}
                </div>
              </div>
            </div>
            <div className="modal-footer" style={{ display: 'flex', gap: '0.5rem', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button className="btn btn-secondary" onClick={handleCopyOutreach}>
                  Copy to Clipboard
                </button>
                <button className="btn btn-secondary" onClick={handleRegenerateOutreach}
                  disabled={generatingId != null}>
                  {generatingId != null ? 'Regenerating...' : 'Regenerate'}
                </button>
              </div>
              <button className="btn btn-secondary" onClick={() => { setOutreachPreview(null); setOutreachSourceItem(null); }}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Intelligence;
