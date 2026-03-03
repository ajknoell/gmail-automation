import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import TabBar from '../components/ui/TabBar';
import {
  getPipelineLeads, getPipelineStats, enrichPipelineLead, bulkEnrichLeads,
  approvePipelineLead, bulkApproveLeads, bulkRejectLeads, deletePipelineLead,
  getCampaigns, getDiscoveryStats,
} from '../api/client';
import { useToast } from '../components/Toast';
import ConfirmDialog from '../components/ConfirmDialog';
import { scoreColor } from '../utils/colors';

const STATUS_LABELS = {
  new: 'New', enriching: 'Enriching...', enriched: 'Enriched',
  qualified: 'Qualified', approved: 'Approved', in_campaign: 'In Campaign', rejected: 'Rejected',
};

function Prospects() {
  const { tab } = useParams();
  const navigate = useNavigate();
  const showToast = useToast();
  const activeTab = tab || 'find';

  const [pipelineStats, setPipelineStats] = useState({});
  const [discoveryStats, setDiscoveryStats] = useState({});

  useEffect(() => {
    getPipelineStats().then(res => setPipelineStats(res.data)).catch(() => {});
    getDiscoveryStats().then(res => setDiscoveryStats(res.data)).catch(() => {});
  }, []);

  const findCount = discoveryStats.total || 0;
  const reviewCount = (pipelineStats.by_status?.new || 0) + (pipelineStats.by_status?.enriching || 0) +
    (pipelineStats.by_status?.enriched || 0) + (pipelineStats.by_status?.qualified || 0);
  const readyCount = (pipelineStats.by_status?.approved || 0) + (pipelineStats.by_status?.in_campaign || 0);

  const tabs = [
    { id: 'find', label: 'Find', count: findCount },
    { id: 'review', label: 'Review & Enrich', count: reviewCount },
    { id: 'ready', label: 'Ready', count: readyCount },
  ];

  return (
    <div style={{ maxWidth: 1400 }}>
      <div className="page-header">
        <div>
          <h1>Prospects</h1>
          <p className="text-sm text-light">Find businesses, enrich with data, approve for outreach</p>
        </div>
        <div className="flex gap-1">
          <Link to="/map-explorer" className="btn btn-secondary">Map Explorer</Link>
          <Link to="/discovery" className="btn btn-secondary">Discovery Criteria</Link>
        </div>
      </div>

      <TabBar
        tabs={tabs}
        activeTab={activeTab}
        onChange={(id) => navigate(id === 'find' ? '/prospects' : `/prospects/${id}`)}
      />

      {activeTab === 'find' && <ProspectFindTab onStatsChange={() => {
        getPipelineStats().then(res => setPipelineStats(res.data)).catch(() => {});
        getDiscoveryStats().then(res => setDiscoveryStats(res.data)).catch(() => {});
      }} />}
      {activeTab === 'review' && <ProspectReviewTab onStatsChange={() => {
        getPipelineStats().then(res => setPipelineStats(res.data)).catch(() => {});
      }} />}
      {activeTab === 'ready' && <ProspectReadyTab onStatsChange={() => {
        getPipelineStats().then(res => setPipelineStats(res.data)).catch(() => {});
      }} />}
    </div>
  );
}

/* ===================== FIND TAB ===================== */
function ProspectFindTab({ onStatsChange }) {
  const showToast = useToast();
  const [recentLeads, setRecentLeads] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getPipelineLeads({ sort: 'created_at', order: 'desc' })
      .then(res => setRecentLeads((res.data.leads || []).slice(0, 10)))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="card mb-4" style={{ textAlign: 'center', padding: '2rem' }}>
        <h3 style={{ marginBottom: '0.5rem' }}>Find New Prospects</h3>
        <p className="text-light" style={{ marginBottom: '1.25rem', maxWidth: 500, margin: '0 auto 1.25rem' }}>
          Search by location on the map, or set up automated discovery criteria to find businesses that match your ideal customer profile.
        </p>
        <div className="flex gap-2 justify-center">
          <Link to="/map-explorer" className="btn btn-primary">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{ marginRight: 4 }}>
              <path d="M8 1C5.24 1 3 3.24 3 6C3 9.5 8 15 8 15S13 9.5 13 6C13 3.24 10.76 1 8 1Z" stroke="currentColor" strokeWidth="1.5"/>
            </svg>
            Search Map
          </Link>
          <Link to="/discovery" className="btn btn-secondary">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{ marginRight: 4 }}>
              <path d="M6.5 11C9 11 11 9 11 6.5S9 2 6.5 2 2 4 2 6.5 4 11 6.5 11ZM11 11L14 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
            Discovery Criteria
          </Link>
        </div>
      </div>

      {recentLeads.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Recently Added to Pipeline</h3>
          </div>
          {loading ? (
            <p className="text-light">Loading...</p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Business</th>
                  <th>Category</th>
                  <th>Rating</th>
                  <th>Status</th>
                  <th>Added</th>
                </tr>
              </thead>
              <tbody>
                {recentLeads.map(lead => (
                  <tr key={lead.id}>
                    <td>
                      <div style={{ fontWeight: 500 }}>{lead.name}</div>
                      {lead.address && <div className="text-sm text-light">{lead.address.slice(0, 50)}</div>}
                    </td>
                    <td>
                      {lead.business_category && (
                        <span className="badge badge-new" style={{ fontSize: '0.6875rem' }}>
                          {lead.business_category.replace(/_/g, ' ')}
                        </span>
                      )}
                    </td>
                    <td>
                      {lead.google_rating ? (
                        <span style={{ color: lead.google_rating >= 4 ? '#D97706' : 'var(--text-light)' }}>
                          {lead.google_rating}
                        </span>
                      ) : '--'}
                    </td>
                    <td><span className={`badge badge-${lead.status}`}>{STATUS_LABELS[lead.status]}</span></td>
                    <td className="text-sm text-light">{new Date(lead.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}

/* ===================== REVIEW TAB ===================== */
function ProspectReviewTab({ onStatsChange }) {
  const showToast = useToast();
  const [leads, setLeads] = useState([]);
  const [campaigns, setCampaigns] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [enrichingIds, setEnrichingIds] = useState(new Set());
  const [search, setSearch] = useState('');
  const [approveModal, setApproveModal] = useState(null);
  const [approveEmail, setApproveEmail] = useState('');
  const [approveCampaignId, setApproveCampaignId] = useState('');
  const [expandedLead, setExpandedLead] = useState(null);
  const [confirmState, setConfirmState] = useState(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [leadsRes, campaignsRes] = await Promise.all([
        getPipelineLeads({ sort: 'created_at', order: 'desc' }),
        getCampaigns(),
      ]);
      // Filter to review-stage leads
      const reviewLeads = (leadsRes.data.leads || []).filter(l =>
        ['new', 'enriching', 'enriched', 'qualified'].includes(l.status)
      );
      setLeads(reviewLeads);
      setCampaigns(campaignsRes.data || []);
    } catch (err) {
      console.error('Review tab load error:', err);
    }
    setLoading(false);
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const filteredLeads = leads.filter(lead => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (lead.name || '').toLowerCase().includes(q) ||
      (lead.business_category || '').toLowerCase().includes(q) ||
      (lead.address || '').toLowerCase().includes(q);
  });

  const toggleSelect = (id) => setSelected(prev => {
    const next = new Set(prev); next.has(id) ? next.delete(id) : next.add(id); return next;
  });

  const handleEnrichOne = async (lead) => {
    setEnrichingIds(prev => new Set([...prev, lead.id]));
    try {
      await enrichPipelineLead(lead.id);
      await loadData();
      onStatsChange();
    } catch (err) {
      showToast('Enrichment failed: ' + (err.response?.data?.error || err.message), 'error');
    }
    setEnrichingIds(prev => { const n = new Set(prev); n.delete(lead.id); return n; });
  };

  const handleBulkEnrich = async () => {
    const ids = [...selected];
    if (!ids.length) return;
    setEnrichingIds(prev => new Set([...prev, ...ids]));
    try {
      const res = await bulkEnrichLeads(ids);
      showToast(`Enriched ${res.data.enriched} of ${res.data.total} leads`, 'success');
      await loadData();
      onStatsChange();
    } catch (err) {
      showToast('Bulk enrich failed', 'error');
    }
    setEnrichingIds(new Set());
  };

  const openApproveModal = (lead) => {
    setApproveEmail((lead.emails_found || [])[0] || '');
    setApproveCampaignId('');
    setApproveModal(lead);
  };

  const handleApprove = async () => {
    if (approveModal === 'bulk') {
      try {
        const res = await bulkApproveLeads({ lead_ids: [...selected], campaign_id: approveCampaignId || undefined });
        showToast(`Approved ${res.data.approved} leads`, 'success');
        setSelected(new Set());
      } catch (err) {
        showToast('Bulk approve failed', 'error');
      }
    } else {
      try {
        await approvePipelineLead(approveModal.id, { email: approveEmail, campaign_id: approveCampaignId || undefined });
        showToast('Lead approved', 'success');
      } catch (err) {
        showToast('Approve failed', 'error');
      }
    }
    setApproveModal(null);
    await loadData();
    onStatsChange();
  };

  const handleBulkReject = () => {
    if (!selected.size) return;
    setConfirmState({
      title: `Reject ${selected.size} leads?`,
      message: 'These leads will be marked as rejected.',
      confirmLabel: 'Reject', confirmClass: 'btn-danger',
      onConfirm: async () => {
        setConfirmState(null);
        try {
          await bulkRejectLeads([...selected]);
          showToast(`${selected.size} leads rejected`, 'success');
          setSelected(new Set());
          await loadData();
          onStatsChange();
        } catch { showToast('Reject failed', 'error'); }
      },
    });
  };

  if (loading) return <div className="card"><p className="text-light" style={{ padding: '2rem', textAlign: 'center' }}>Loading leads...</p></div>;

  return (
    <div>
      {/* Search + bulk actions */}
      <div className="toolbar">
        <input type="text" className="form-input" placeholder="Search leads..."
          value={search} onChange={e => setSearch(e.target.value)}
          style={{ maxWidth: 300, border: 'none', background: 'var(--bg-white)', boxShadow: 'var(--shadow)', borderRadius: '0.5rem' }} />
        <div className="toolbar-spacer" />
        {selected.size > 0 && (
          <>
            <span className="toolbar-count">{selected.size} selected</span>
            <button className="btn btn-primary btn-sm" onClick={handleBulkEnrich}>Enrich</button>
            <button className="btn btn-success btn-sm" onClick={() => { setApproveEmail(''); setApproveCampaignId(''); setApproveModal('bulk'); }}>Approve</button>
            <button className="btn btn-danger btn-sm" onClick={handleBulkReject}>Reject</button>
          </>
        )}
      </div>

      {leads.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="empty-state-icon">V</div>
            <p>No leads to review yet</p>
            <p className="text-sm text-light">Find prospects on the Map or via Discovery, then come back here to enrich and approve them.</p>
          </div>
        </div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <table className="table">
            <thead>
              <tr>
                <th style={{ width: 40 }}>
                  <input type="checkbox"
                    checked={selected.size === filteredLeads.length && filteredLeads.length > 0}
                    onChange={() => selected.size === filteredLeads.length ? setSelected(new Set()) : setSelected(new Set(filteredLeads.map(l => l.id)))} />
                </th>
                <th>Business</th>
                <th>Enrichment</th>
                <th>Score</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredLeads.map(lead => {
                const emails = lead.emails_found || [];
                return (
                  <tr key={lead.id} style={{ cursor: 'pointer' }} onClick={() => setExpandedLead(expandedLead === lead.id ? null : lead.id)}>
                    <td onClick={e => e.stopPropagation()}>
                      <input type="checkbox" checked={selected.has(lead.id)} onChange={() => toggleSelect(lead.id)} />
                    </td>
                    <td>
                      <div style={{ fontWeight: 500 }}>{lead.name}</div>
                      {lead.address && <div className="text-sm text-light">{lead.address.slice(0, 40)}</div>}
                      {lead.business_category && (
                        <span className="badge badge-new" style={{ marginTop: 2, display: 'inline-block', fontSize: '0.6875rem' }}>
                          {lead.business_category.replace(/_/g, ' ')}
                        </span>
                      )}
                    </td>
                    <td>
                      <div className="flex items-center gap-1" style={{ flexWrap: 'wrap' }}>
                        {lead.employee_count ? <span className="badge" style={{ background: '#FFF1EC', color: '#C2410C' }}>{lead.employee_count} emp</span> : null}
                        {emails.length > 0 ? <span className="badge" style={{ background: '#D1FAE5', color: '#065F46' }}>Email</span> : null}
                        {lead.linkedin_url ? <span className="badge" style={{ background: '#DBEAFE', color: '#1E40AF' }}>LinkedIn</span> : null}
                        {!lead.employee_count && !emails.length && !lead.linkedin_url && <span className="text-sm text-light">{lead.status === 'new' ? 'Pending' : '--'}</span>}
                      </div>
                    </td>
                    <td>
                      {lead.score != null ? (
                        <span className="badge" style={{ fontWeight: 600, color: scoreColor(lead.score), background: scoreColor(lead.score) + '18' }}>
                          {lead.score}
                        </span>
                      ) : <span className="text-light">--</span>}
                    </td>
                    <td><span className={`badge badge-${lead.status}`}>{STATUS_LABELS[lead.status]}</span></td>
                    <td onClick={e => e.stopPropagation()}>
                      <div className="flex gap-1">
                        {['new', 'enriched'].includes(lead.status) && (
                          <button className="btn btn-primary btn-sm" onClick={() => handleEnrichOne(lead)} disabled={enrichingIds.has(lead.id)}>
                            {enrichingIds.has(lead.id) ? '...' : 'Enrich'}
                          </button>
                        )}
                        {['enriched', 'qualified'].includes(lead.status) && (
                          <button className="btn btn-success btn-sm" onClick={() => openApproveModal(lead)}>Approve</button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Approve Modal */}
      {approveModal && (
        <div className="modal-overlay" onClick={() => setApproveModal(null)}>
          <div className="modal" style={{ maxWidth: 440 }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">{approveModal === 'bulk' ? `Approve ${selected.size} Leads` : `Approve: ${approveModal.name}`}</h3>
              <button className="modal-close" onClick={() => setApproveModal(null)}>&times;</button>
            </div>
            <div className="modal-body">
              {approveModal !== 'bulk' && (
                <div className="form-group">
                  <label className="form-label">Email Address *</label>
                  <input type="email" className="form-input" value={approveEmail}
                    onChange={e => setApproveEmail(e.target.value)} placeholder="contact@business.com" />
                  {approveModal.emails_found?.length > 0 && (
                    <div className="mt-1 text-sm text-light">
                      Found: {approveModal.emails_found.map((e, i) => (
                        <span key={i} onClick={() => setApproveEmail(e)} style={{ cursor: 'pointer', color: 'var(--primary)', marginRight: 8 }}>{e}</span>
                      ))}
                    </div>
                  )}
                </div>
              )}
              <div className="form-group">
                <label className="form-label">Add to Campaign (optional)</label>
                <select className="form-select" value={approveCampaignId} onChange={e => setApproveCampaignId(e.target.value)}>
                  <option value="">Don't add to campaign</option>
                  {campaigns.map(c => <option key={c.id} value={c.id}>{c.name} ({c.status})</option>)}
                </select>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setApproveModal(null)}>Cancel</button>
              <button className="btn btn-success" onClick={handleApprove}>Approve</button>
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog open={!!confirmState} {...confirmState} onCancel={() => setConfirmState(null)} />
    </div>
  );
}

/* ===================== READY TAB ===================== */
function ProspectReadyTab({ onStatsChange }) {
  const showToast = useToast();
  const [leads, setLeads] = useState([]);
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [leadsRes, campaignsRes] = await Promise.all([
        getPipelineLeads({ sort: 'score', order: 'desc' }),
        getCampaigns(),
      ]);
      const readyLeads = (leadsRes.data.leads || []).filter(l =>
        ['approved', 'in_campaign'].includes(l.status)
      );
      setLeads(readyLeads);
      setCampaigns(campaignsRes.data || []);
    } catch (err) {
      console.error('Ready tab load error:', err);
    }
    setLoading(false);
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleQuickSend = (lead) => {
    const emails = lead.emails_found || [];
    window.dispatchEvent(new CustomEvent('open-quick-send', {
      detail: {
        name: lead.decision_maker || lead.name,
        email: emails[0] || '',
        company: lead.name,
        website: lead.website || '',
      }
    }));
  };

  if (loading) return <div className="card"><p className="text-light" style={{ padding: '2rem', textAlign: 'center' }}>Loading...</p></div>;

  return (
    <div>
      {leads.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="empty-state-icon">V</div>
            <p>No leads approved yet</p>
            <p className="text-sm text-light">Go to the Review tab to enrich and approve leads, then they'll show up here ready for outreach.</p>
          </div>
        </div>
      ) : (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1rem' }}>
            {leads.map(lead => {
              const emails = lead.emails_found || [];
              return (
                <div key={lead.id} className="card" style={{ padding: '1rem 1.25rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                    <div>
                      <div style={{ fontWeight: 600 }}>{lead.name}</div>
                      {lead.business_category && (
                        <span className="text-sm text-light">{lead.business_category.replace(/_/g, ' ')}</span>
                      )}
                    </div>
                    {lead.score != null && (
                      <span className="badge" style={{
                        fontWeight: 600,
                        color: lead.score >= 70 ? '#10B981' : lead.score >= 40 ? '#F59E0B' : '#EF4444',
                        background: (lead.score >= 70 ? '#10B981' : lead.score >= 40 ? '#F59E0B' : '#EF4444') + '18',
                      }}>
                        Score: {lead.score}
                      </span>
                    )}
                  </div>

                  {emails.length > 0 && (
                    <div className="text-sm" style={{ marginBottom: '0.375rem' }}>
                      <span className="text-light">Email: </span>{emails[0]}
                    </div>
                  )}
                  {lead.decision_maker && (
                    <div className="text-sm" style={{ marginBottom: '0.375rem' }}>
                      <span className="text-light">Contact: </span>{lead.decision_maker}
                    </div>
                  )}
                  {lead.phone && (
                    <div className="text-sm" style={{ marginBottom: '0.375rem' }}>
                      <span className="text-light">Phone: </span>{lead.phone}
                    </div>
                  )}

                  <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.5rem' }}>
                    {emails.length > 0 && (
                      <button className="btn btn-primary btn-sm" onClick={() => handleQuickSend(lead)}>
                        Quick Send
                      </button>
                    )}
                    <span className={`badge badge-${lead.status}`} style={{ alignSelf: 'center' }}>
                      {STATUS_LABELS[lead.status]}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

export default Prospects;
