import { useState, useEffect, useCallback } from 'react';
import {
  getPipelineLeads, getPipelineStats, enrichPipelineLead, bulkEnrichLeads,
  approvePipelineLead, bulkApproveLeads, bulkRejectLeads, deletePipelineLead,
  getCampaigns,
} from '../api/client';
import { useToast } from '../components/Toast';
import ConfirmDialog from '../components/ConfirmDialog';
import { scoreColor } from '../utils/colors';

const STATUS_LABELS = {
  new: 'New',
  enriching: 'Enriching...',
  enriched: 'Enriched',
  qualified: 'Qualified',
  approved: 'Approved',
  in_campaign: 'In Campaign',
  rejected: 'Rejected',
};

function Pipeline() {
  const [leads, setLeads] = useState([]);
  const [stats, setStats] = useState({});
  const [campaigns, setCampaigns] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [enrichingIds, setEnrichingIds] = useState(new Set());
  const [filter, setFilter] = useState({ status: '', min_score: '', retirement_label: '' });
  const [sort, setSort] = useState({ by: 'created_at', order: 'desc' });
  const [search, setSearch] = useState('');
  const [approveModal, setApproveModal] = useState(null);
  const [approveEmail, setApproveEmail] = useState('');
  const [approveCampaignId, setApproveCampaignId] = useState('');
  const [expandedLead, setExpandedLead] = useState(null);
  const [confirmState, setConfirmState] = useState(null);
  const showToast = useToast();

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const params = { sort: sort.by, order: sort.order };
      if (filter.status) params.status = filter.status;
      if (filter.min_score) params.min_score = filter.min_score;
      if (filter.retirement_label) params.retirement_label = filter.retirement_label;

      const [leadsRes, statsRes, campaignsRes] = await Promise.all([
        getPipelineLeads(params),
        getPipelineStats(),
        getCampaigns(),
      ]);
      setLeads(leadsRes.data.leads || []);
      setStats(statsRes.data);
      setCampaigns(campaignsRes.data || []);
    } catch (err) {
      console.error('Pipeline load error:', err);
    }
    setLoading(false);
  }, [filter, sort]);

  useEffect(() => { loadData(); }, [loadData]);

  const filteredLeads = leads.filter(lead => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      (lead.name || '').toLowerCase().includes(q) ||
      (lead.business_category || '').toLowerCase().includes(q) ||
      (lead.address || '').toLowerCase().includes(q) ||
      (lead.emails_found || []).some(e => e.toLowerCase().includes(q))
    );
  });

  const toggleSelect = (id) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selected.size === filteredLeads.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(filteredLeads.map(l => l.id)));
    }
  };

  const handleEnrichOne = async (lead) => {
    setEnrichingIds(prev => new Set([...prev, lead.id]));
    try {
      await enrichPipelineLead(lead.id);
      await loadData();
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
    } catch (err) {
      showToast('Bulk enrich failed: ' + (err.response?.data?.error || err.message), 'error');
    }
    setEnrichingIds(new Set());
  };

  const openApproveModal = (lead) => {
    const emails = lead.emails_found || [];
    setApproveEmail(emails[0] || '');
    setApproveCampaignId('');
    setApproveModal(lead);
  };

  const openBulkApproveModal = () => {
    setApproveEmail('');
    setApproveCampaignId('');
    setApproveModal('bulk');
  };

  const handleApprove = async () => {
    if (approveModal === 'bulk') {
      try {
        const res = await bulkApproveLeads({
          lead_ids: [...selected],
          campaign_id: approveCampaignId || undefined,
        });
        showToast(`Approved ${res.data.approved} leads (${res.data.skipped} skipped)`, 'success');
        setSelected(new Set());
      } catch (err) {
        showToast('Bulk approve failed: ' + (err.response?.data?.error || err.message), 'error');
      }
    } else {
      try {
        await approvePipelineLead(approveModal.id, {
          email: approveEmail,
          campaign_id: approveCampaignId || undefined,
        });
        showToast('Lead approved successfully', 'success');
      } catch (err) {
        showToast('Approve failed: ' + (err.response?.data?.error || err.message), 'error');
      }
    }
    setApproveModal(null);
    await loadData();
  };

  const handleBulkReject = () => {
    if (!selected.size) return;
    setConfirmState({
      title: `Reject ${selected.size} leads?`,
      message: 'These leads will be marked as rejected.',
      confirmLabel: 'Reject',
      confirmClass: 'btn-danger',
      onConfirm: async () => {
        setConfirmState(null);
        try {
          await bulkRejectLeads([...selected]);
          showToast(`${selected.size} leads rejected`, 'success');
          setSelected(new Set());
          await loadData();
        } catch (err) {
          showToast('Reject failed', 'error');
        }
      },
    });
  };

  const handleDelete = (id) => {
    setConfirmState({
      title: 'Delete this lead?',
      message: 'This action cannot be undone.',
      confirmLabel: 'Delete',
      confirmClass: 'btn-danger',
      onConfirm: async () => {
        setConfirmState(null);
        await deletePipelineLead(id);
        showToast('Lead deleted', 'info');
        loadData();
      },
    });
  };

  const retirementColor = (label) => {
    if (label === 'high') return '#F59E0B';
    if (label === 'medium') return '#3B82F6';
    return '#6B7280';
  };

  if (loading) {
    return (
      <div style={{ maxWidth: 1400 }}>
        <div className="page-header">
          <div>
            <h1>Lead Pipeline</h1>
            <p className="text-sm text-light">Discover, enrich, and qualify leads before outbound</p>
          </div>
        </div>
        <div className="grid mb-4" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))' }}>
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="card stat-card-compact">
              <div className="skeleton skeleton-text-sm" style={{ width: '50%' }} />
              <div className="skeleton skeleton-text" style={{ width: '40%', height: '1.5rem' }} />
            </div>
          ))}
        </div>
        <div className="card" style={{ padding: 0 }}>
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex gap-2 items-center" style={{ padding: '0.75rem 1rem', borderBottom: '1px solid var(--border)' }}>
              <div className="skeleton" style={{ width: 16, height: 16, flexShrink: 0 }} />
              <div style={{ flex: 1 }}>
                <div className="skeleton skeleton-text" style={{ width: '30%' }} />
                <div className="skeleton skeleton-text-sm" />
              </div>
              <div className="skeleton skeleton-text" style={{ width: '8%' }} />
              <div className="skeleton skeleton-text" style={{ width: '8%' }} />
              <div className="skeleton skeleton-text" style={{ width: '6%' }} />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 1400 }}>
      <div className="page-header">
        <div>
          <h1>Lead Pipeline</h1>
          <p className="text-sm text-light">
            Discover, enrich, and qualify leads before outbound
          </p>
        </div>
      </div>

      {/* Stats cards */}
      <div className="grid mb-4" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))' }}>
        <StatCard label="Total Leads" value={stats.total || 0} />
        <StatCard label="New" value={stats.by_status?.new || 0} color="#6B7280" />
        <StatCard label="Enriched" value={(stats.by_status?.enriched || 0) + (stats.by_status?.qualified || 0)} color="#3B82F6" />
        <StatCard label="Approved" value={(stats.by_status?.approved || 0) + (stats.by_status?.in_campaign || 0)} color="#10B981" />
        <StatCard label="Avg Score" value={stats.avg_score || 0} color="#E8603C" />
        <StatCard label="Has Email" value={stats.with_email || 0} color="#0891B2" />
        <StatCard label="Has Employee #" value={stats.with_employee_count || 0} color="#8B5CF6" />
        <StatCard label="Likely Retiring" value={stats.with_high_retirement || 0} color="#F59E0B" />
      </div>

      {/* Search */}
      <div className="card mb-2" style={{ padding: '0.75rem 1rem' }}>
        <input
          type="text"
          className="form-input"
          placeholder="Search leads by name, category, address, or email..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{ border: 'none', padding: 0, boxShadow: 'none' }}
        />
      </div>

      {/* Filters and bulk actions */}
      <div className="toolbar">
        <select
          className="form-select"
          style={{ width: 'auto' }}
          value={filter.status}
          onChange={e => setFilter(f => ({ ...f, status: e.target.value }))}
        >
          <option value="">All Statuses</option>
          <option value="new">New</option>
          <option value="enriching">Enriching</option>
          <option value="enriched">Enriched</option>
          <option value="qualified">Qualified</option>
          <option value="approved">Approved</option>
          <option value="in_campaign">In Campaign</option>
          <option value="rejected">Rejected</option>
        </select>

        <select
          className="form-select"
          style={{ width: 'auto' }}
          value={filter.min_score}
          onChange={e => setFilter(f => ({ ...f, min_score: e.target.value }))}
        >
          <option value="">Any Score</option>
          <option value="30">30+</option>
          <option value="50">50+</option>
          <option value="60">60+ (Qualified)</option>
          <option value="70">70+</option>
          <option value="80">80+</option>
        </select>

        <select
          className="form-select"
          style={{ width: 'auto' }}
          value={filter.retirement_label}
          onChange={e => setFilter(f => ({ ...f, retirement_label: e.target.value }))}
        >
          <option value="">Any Retirement</option>
          <option value="high">Likely Retiring</option>
          <option value="medium">Maybe Retiring</option>
          <option value="low">Unlikely</option>
        </select>

        <select
          className="form-select"
          style={{ width: 'auto' }}
          value={`${sort.by}:${sort.order}`}
          onChange={e => {
            const [by, order] = e.target.value.split(':');
            setSort({ by, order });
          }}
        >
          <option value="created_at:desc">Newest First</option>
          <option value="created_at:asc">Oldest First</option>
          <option value="score:desc">Highest Score</option>
          <option value="score:asc">Lowest Score</option>
          <option value="retirement_score:desc">Highest Retirement</option>
          <option value="retirement_score:asc">Lowest Retirement</option>
          <option value="employee_count:desc">Most Employees</option>
          <option value="employee_count:asc">Fewest Employees</option>
        </select>

        <div className="toolbar-spacer" />

        {selected.size > 0 && (
          <>
            <span className="toolbar-count">{selected.size} selected</span>
            <button className="btn btn-primary btn-sm" onClick={handleBulkEnrich}>
              Enrich Selected
            </button>
            <button className="btn btn-success btn-sm" onClick={openBulkApproveModal}>
              Approve Selected
            </button>
            <button className="btn btn-danger btn-sm" onClick={handleBulkReject}>
              Reject
            </button>
          </>
        )}
      </div>

      {/* Leads table */}
      {leads.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="empty-state-icon">🔍</div>
            <p>No leads in your pipeline yet</p>
            <p className="text-sm text-light">
              Go to <strong>Map Explorer</strong> and click "Add to Pipeline" on businesses you want to prospect.
            </p>
          </div>
        </div>
      ) : filteredLeads.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="empty-state-icon">🔍</div>
            <p>No leads match your filters</p>
            <button
              className="btn btn-secondary mt-2"
              onClick={() => { setSearch(''); setFilter({ status: '', min_score: '' }); }}
            >
              Clear Filters
            </button>
          </div>
        </div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <table className="table">
            <thead>
              <tr>
                <th style={{ width: 40 }}>
                  <input
                    type="checkbox"
                    checked={selected.size === filteredLeads.length && filteredLeads.length > 0}
                    onChange={toggleSelectAll}
                  />
                </th>
                <th>Business</th>
                <th>Rating</th>
                <th>Enrichment</th>
                <th>Score</th>
                <th>Retirement</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredLeads.map(lead => (
                <LeadRow
                  key={lead.id}
                  lead={lead}
                  selected={selected.has(lead.id)}
                  onToggle={() => toggleSelect(lead.id)}
                  onEnrich={() => handleEnrichOne(lead)}
                  onApprove={() => openApproveModal(lead)}
                  onDelete={() => handleDelete(lead.id)}
                  enriching={enrichingIds.has(lead.id)}
                  expanded={expandedLead === lead.id}
                  onExpand={() => setExpandedLead(expandedLead === lead.id ? null : lead.id)}
                  scoreColor={scoreColor}
                  retirementColor={retirementColor}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Approve Modal */}
      {approveModal && (
        <div className="modal-overlay" onClick={() => setApproveModal(null)}>
          <div className="modal" style={{ maxWidth: 440 }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">
                {approveModal === 'bulk'
                  ? `Approve ${selected.size} Leads`
                  : `Approve: ${approveModal.name}`}
              </h3>
              <button className="modal-close" onClick={() => setApproveModal(null)}>&times;</button>
            </div>

            <div className="modal-body">
              {approveModal !== 'bulk' && (
                <div className="form-group">
                  <label className="form-label">Email Address *</label>
                  <input
                    type="email"
                    className="form-input"
                    value={approveEmail}
                    onChange={e => setApproveEmail(e.target.value)}
                    placeholder="contact@business.com"
                  />
                  {approveModal.emails_found?.length > 0 && (
                    <div className="mt-1 text-sm text-light">
                      Found:{' '}
                      {approveModal.emails_found.map((e, i) => (
                        <span
                          key={i}
                          onClick={() => setApproveEmail(e)}
                          style={{ cursor: 'pointer', color: 'var(--primary)', marginRight: 8 }}
                        >
                          {e}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <div className="form-group">
                <label className="form-label">Add to Campaign (optional)</label>
                <select
                  className="form-select"
                  value={approveCampaignId}
                  onChange={e => setApproveCampaignId(e.target.value)}
                >
                  <option value="">Don't add to campaign</option>
                  {campaigns.map(c => (
                    <option key={c.id} value={c.id}>
                      {c.name} ({c.status})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setApproveModal(null)}>
                Cancel
              </button>
              <button className="btn btn-success" onClick={handleApprove}>
                Approve & Create Contact
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Confirm Dialog */}
      <ConfirmDialog
        open={!!confirmState}
        {...confirmState}
        onCancel={() => setConfirmState(null)}
      />
    </div>
  );
}

function LeadRow({ lead, selected, onToggle, onEnrich, onApprove, onDelete, enriching, expanded, onExpand, scoreColor, retirementColor }) {
  const emails = lead.emails_found || [];
  const hasEmail = emails.length > 0;

  return (
    <>
      <tr style={{ cursor: 'pointer' }} onClick={onExpand}>
        <td onClick={e => e.stopPropagation()}>
          <input type="checkbox" checked={selected} onChange={onToggle} />
        </td>
        <td>
          <div style={{ fontWeight: 500 }}>{lead.name}</div>
          <div className="text-sm text-light" style={{ marginTop: 2 }}>
            {lead.address ? (lead.address.length > 40 ? lead.address.slice(0, 40) + '...' : lead.address) : ''}
          </div>
          {lead.business_category && (
            <span className="badge badge-new" style={{ marginTop: 4, display: 'inline-block', fontSize: '0.6875rem' }}>
              {lead.business_category.replace(/_/g, ' ')}
            </span>
          )}
        </td>
        <td>
          {lead.google_rating ? (
            <span style={{ color: lead.google_rating >= 4 ? '#D97706' : 'var(--text-light)' }}>
              {lead.google_rating} <span className="text-light">({lead.review_count || 0})</span>
            </span>
          ) : <span className="text-light">--</span>}
        </td>
        <td>
          <div className="flex items-center gap-1" style={{ flexWrap: 'wrap' }}>
            {lead.employee_count ? (
              <span className="badge" style={{ background: '#FFF1EC', color: '#C2410C' }}>
                {lead.employee_count} emp
              </span>
            ) : null}
            {hasEmail ? (
              <span className="badge" style={{ background: '#D1FAE5', color: '#065F46' }} title={emails[0]}>
                Email
              </span>
            ) : lead.status !== 'new' ? (
              <span className="text-light text-sm">No email</span>
            ) : null}
            {lead.linkedin_url ? (
              <a
                href={lead.linkedin_url}
                target="_blank"
                rel="noopener noreferrer"
                className="badge"
                style={{ background: '#DBEAFE', color: '#1E40AF', textDecoration: 'none' }}
                onClick={e => e.stopPropagation()}
              >
                LinkedIn
              </a>
            ) : null}
            {!lead.employee_count && !hasEmail && !lead.linkedin_url && (
              <span className="text-light text-sm">{lead.status === 'new' ? 'Pending' : '--'}</span>
            )}
          </div>
        </td>
        <td>
          {lead.score != null ? (
            <span
              className="badge"
              style={{
                fontWeight: 600,
                color: scoreColor(lead.score),
                background: scoreColor(lead.score) + '18',
              }}
            >
              {lead.score}
            </span>
          ) : <span className="text-light">--</span>}
        </td>
        <td>
          {lead.retirement_score != null ? (
            <span style={{
              fontWeight: 600,
              color: retirementColor(lead.retirement_label),
              background: retirementColor(lead.retirement_label) + '20',
              padding: '2px 8px',
              borderRadius: 4,
              fontSize: '0.75rem',
            }}>
              {lead.retirement_label === 'high' ? 'Likely' :
               lead.retirement_label === 'medium' ? 'Maybe' :
               lead.retirement_label === 'low' ? 'Unlikely' : '?'}
              <span style={{ fontSize: '0.625rem', marginLeft: 4, opacity: 0.7 }}>
                {lead.retirement_score}
              </span>
            </span>
          ) : (
            <span className="text-light">{lead.status === 'new' ? '' : '—'}</span>
          )}
        </td>
        <td>
          <span className={`badge badge-${lead.status}`}>
            {STATUS_LABELS[lead.status] || lead.status}
          </span>
        </td>
        <td onClick={e => e.stopPropagation()}>
          <div className="flex gap-1">
            {['new', 'enriched'].includes(lead.status) && (
              <button
                className="btn btn-primary btn-sm"
                onClick={onEnrich}
                disabled={enriching}
              >
                {enriching ? 'Enriching...' : 'Enrich'}
              </button>
            )}
            {['enriched', 'qualified'].includes(lead.status) && (
              <button className="btn btn-success btn-sm" onClick={onApprove}>
                Approve
              </button>
            )}
            <button className="btn btn-danger btn-sm" onClick={onDelete}>
              Delete
            </button>
          </div>
        </td>
      </tr>

      {/* Expanded detail row */}
      {expanded && (
        <tr>
          <td colSpan={8} style={{ background: 'var(--bg)', padding: 0 }}>
            <div style={{ padding: '1rem 1.5rem' }}>
              <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
                <div>
                  <h4 className="text-light" style={{ margin: '0 0 8px', fontWeight: 500, fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.03em' }}>
                    Contact Info
                  </h4>
                  <Detail label="Phone" value={lead.phone} />
                  <Detail label="Website" value={lead.website} link />
                  <Detail label="Address" value={lead.address} />
                </div>
                <div>
                  <h4 className="text-light" style={{ margin: '0 0 8px', fontWeight: 500, fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.03em' }}>
                    Enrichment Data
                  </h4>
                  <Detail label="Employees" value={lead.employee_count ? `${lead.employee_count} (via ${lead.employee_count_source})` : null} />
                  <Detail label="LinkedIn" value={lead.linkedin_url} link />
                  <Detail label="Decision Maker" value={lead.decision_maker} />
                  <Detail label="Year Founded" value={lead.year_founded} />
                  <Detail label="Emails Found" value={emails.join(', ') || null} />
                </div>
                <div>
                  <h4 className="text-light" style={{ margin: '0 0 8px', fontWeight: 500, fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.03em' }}>
                    Score Breakdown
                  </h4>
                  {lead.score_breakdown && Object.entries(lead.score_breakdown).map(([key, val]) => (
                    <div key={key} className="flex justify-between" style={{ marginBottom: 4, fontSize: '0.8125rem' }}>
                      <span>{key.replace(/_/g, ' ')}</span>
                      <span style={{ color: 'var(--success)', fontWeight: 500 }}>+{val}</span>
                    </div>
                  ))}
                  {(!lead.score_breakdown || Object.keys(lead.score_breakdown).length === 0) && (
                    <span className="text-light text-sm">Not scored yet</span>
                  )}
                </div>
                <div>
                  <h4 className="text-light" style={{ margin: '0 0 8px', fontWeight: 500, fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.03em' }}>
                    Retirement Signals
                  </h4>
                  {lead.retirement_score != null ? (
                    <>
                      <Detail label="Score" value={`${lead.retirement_score}/100 (${lead.retirement_label})`} />
                      {lead.enrichment_data?.retirement_signals?.analysis?.key_evidence?.map((ev, i) => (
                        <div key={i} style={{ marginBottom: 4 }} className="text-sm">
                          <span className="text-light">Signal: </span>
                          <span>{ev}</span>
                        </div>
                      ))}
                      {(!lead.enrichment_data?.retirement_signals?.analysis?.key_evidence?.length) && (
                        <span className="text-light text-sm">No specific signals found</span>
                      )}
                    </>
                  ) : (
                    <span className="text-light text-sm">Not assessed yet</span>
                  )}
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function Detail({ label, value, link }) {
  if (!value) return (
    <div style={{ marginBottom: 4 }} className="text-sm">
      <span className="text-light">{label}: --</span>
    </div>
  );
  return (
    <div style={{ marginBottom: 4 }} className="text-sm">
      <span className="text-light">{label}: </span>
      {link ? (
        <a href={value.startsWith('http') ? value : `https://${value}`} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--primary)' }}>
          {value.length > 40 ? value.slice(0, 40) + '...' : value}
        </a>
      ) : (
        <span>{value}</span>
      )}
    </div>
  );
}

function StatCard({ label, value, color }) {
  return (
    <div
      className={`card stat-card-compact${color ? ' stat-card-accent' : ''}`}
      style={color ? { '--stat-accent': color } : undefined}
    >
      <div className="stat-label">{label}</div>
      <div className="stat-value" style={{ color: color || 'var(--text)' }}>{value}</div>
    </div>
  );
}

export default Pipeline;
