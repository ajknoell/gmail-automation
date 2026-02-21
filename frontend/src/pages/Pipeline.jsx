import { useState, useEffect, useCallback } from 'react';
import {
  getPipelineLeads, getPipelineStats, enrichPipelineLead, bulkEnrichLeads,
  approvePipelineLead, bulkApproveLeads, bulkRejectLeads, deletePipelineLead,
  getCampaigns,
} from '../api/client';

const STATUS_LABELS = {
  new: 'New',
  enriching: 'Enriching...',
  enriched: 'Enriched',
  qualified: 'Qualified',
  approved: 'Approved',
  in_campaign: 'In Campaign',
  rejected: 'Rejected',
};

const STATUS_BADGE_CLASS = {
  new: 'badge-pending',
  enriching: 'badge-paused',
  enriched: 'badge-running',
  qualified: 'badge-draft',
  approved: 'badge-completed',
  in_campaign: 'badge-sent',
  rejected: 'badge-failed',
};

function Pipeline() {
  const [leads, setLeads] = useState([]);
  const [stats, setStats] = useState({});
  const [campaigns, setCampaigns] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [enrichingIds, setEnrichingIds] = useState(new Set());
  const [filter, setFilter] = useState({ status: '', min_score: '' });
  const [sort, setSort] = useState({ by: 'created_at', order: 'desc' });
  const [approveModal, setApproveModal] = useState(null);
  const [approveEmail, setApproveEmail] = useState('');
  const [approveCampaignId, setApproveCampaignId] = useState('');
  const [expandedLead, setExpandedLead] = useState(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const params = { sort: sort.by, order: sort.order };
      if (filter.status) params.status = filter.status;
      if (filter.min_score) params.min_score = filter.min_score;

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

  const toggleSelect = (id) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selected.size === leads.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(leads.map(l => l.id)));
    }
  };

  const handleEnrichOne = async (lead) => {
    setEnrichingIds(prev => new Set([...prev, lead.id]));
    try {
      await enrichPipelineLead(lead.id);
      await loadData();
    } catch (err) {
      alert('Enrichment failed: ' + (err.response?.data?.error || err.message));
    }
    setEnrichingIds(prev => { const n = new Set(prev); n.delete(lead.id); return n; });
  };

  const handleBulkEnrich = async () => {
    const ids = [...selected];
    if (!ids.length) return;
    setEnrichingIds(prev => new Set([...prev, ...ids]));
    try {
      const res = await bulkEnrichLeads(ids);
      alert(`Enriched ${res.data.enriched} of ${res.data.total} leads`);
      await loadData();
    } catch (err) {
      alert('Bulk enrich failed: ' + (err.response?.data?.error || err.message));
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
        alert(`Approved ${res.data.approved} leads (${res.data.skipped} skipped — no email)`);
        setSelected(new Set());
      } catch (err) {
        alert('Bulk approve failed: ' + (err.response?.data?.error || err.message));
      }
    } else {
      try {
        await approvePipelineLead(approveModal.id, {
          email: approveEmail,
          campaign_id: approveCampaignId || undefined,
        });
      } catch (err) {
        alert('Approve failed: ' + (err.response?.data?.error || err.message));
      }
    }
    setApproveModal(null);
    await loadData();
  };

  const handleBulkReject = async () => {
    if (!selected.size) return;
    if (!confirm(`Reject ${selected.size} leads?`)) return;
    try {
      await bulkRejectLeads([...selected]);
      setSelected(new Set());
      await loadData();
    } catch (err) {
      alert('Reject failed');
    }
  };

  const handleDelete = async (id) => {
    if (!confirm('Delete this lead?')) return;
    await deletePipelineLead(id);
    loadData();
  };

  if (loading) {
    return (
      <div style={{ padding: '2rem' }}>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 600, marginBottom: '0.5rem' }}>Lead Pipeline</h1>
        <p className="text-light">Loading...</p>
      </div>
    );
  }

  return (
    <div style={{ padding: '2rem', maxWidth: 1400 }}>
      <div className="page-header">
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 600, margin: 0 }}>Lead Pipeline</h1>
          <p className="text-light" style={{ margin: '0.25rem 0 0', fontSize: '0.875rem' }}>
            Discover, enrich, and qualify leads before outbound
          </p>
        </div>
      </div>

      {/* Stats cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.75rem', marginBottom: '1.5rem' }}>
        <StatCard label="Total Leads" value={stats.total || 0} />
        <StatCard label="New" value={stats.by_status?.new || 0} accent="var(--text-light)" />
        <StatCard label="Enriched" value={(stats.by_status?.enriched || 0) + (stats.by_status?.qualified || 0)} accent="#3B82F6" />
        <StatCard label="Qualified" value={stats.by_status?.qualified || 0} accent="#8B5CF6" />
        <StatCard label="Approved" value={(stats.by_status?.approved || 0) + (stats.by_status?.in_campaign || 0)} accent="var(--success)" />
        <StatCard label="Avg Score" value={stats.avg_score || 0} />
        <StatCard label="Has Email" value={stats.with_email || 0} accent="#059669" />
        <StatCard label="Has Employee #" value={stats.with_employee_count || 0} accent="#7C3AED" />
      </div>

      {/* Filters and bulk actions */}
      <div className="flex items-center gap-1" style={{ marginBottom: '1rem', flexWrap: 'wrap' }}>
        <select
          className="input"
          value={filter.status}
          onChange={e => setFilter(f => ({ ...f, status: e.target.value }))}
          style={{ width: 'auto' }}
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
          className="input"
          value={filter.min_score}
          onChange={e => setFilter(f => ({ ...f, min_score: e.target.value }))}
          style={{ width: 'auto' }}
        >
          <option value="">Any Score</option>
          <option value="30">30+</option>
          <option value="50">50+</option>
          <option value="60">60+ (Qualified)</option>
          <option value="70">70+</option>
          <option value="80">80+</option>
        </select>

        <select
          className="input"
          value={`${sort.by}:${sort.order}`}
          onChange={e => {
            const [by, order] = e.target.value.split(':');
            setSort({ by, order });
          }}
          style={{ width: 'auto' }}
        >
          <option value="created_at:desc">Newest First</option>
          <option value="created_at:asc">Oldest First</option>
          <option value="score:desc">Highest Score</option>
          <option value="score:asc">Lowest Score</option>
          <option value="employee_count:desc">Most Employees</option>
          <option value="employee_count:asc">Fewest Employees</option>
        </select>

        <div style={{ flex: 1 }} />

        {selected.size > 0 && (
          <>
            <span className="text-light text-sm">{selected.size} selected</span>
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
        <div className="empty-state card">
          <p style={{ fontSize: '1rem', marginBottom: '0.5rem' }}>No leads in your pipeline yet</p>
          <p className="text-sm text-light">
            Go to <strong>Map Explorer</strong> and click "Add to Pipeline" on businesses you want to prospect.
          </p>
        </div>
      ) : (
        <div className="card" style={{ overflow: 'hidden', padding: 0 }}>
          <table className="table" style={{ fontSize: '0.8125rem' }}>
            <thead>
              <tr>
                <th style={{ width: 40 }}>
                  <input
                    type="checkbox"
                    checked={selected.size === leads.length && leads.length > 0}
                    onChange={toggleSelectAll}
                  />
                </th>
                <th>Business</th>
                <th>Category</th>
                <th>Rating</th>
                <th>Employees</th>
                <th>Email</th>
                <th>LinkedIn</th>
                <th>Score</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {leads.map(lead => (
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
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Approve Modal */}
      {approveModal && (
        <div className="modal-overlay" onClick={() => setApproveModal(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
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
                    <div style={{ marginTop: '0.25rem', fontSize: '0.75rem' }} className="text-light">
                      Found: {approveModal.emails_found.map((e, i) => (
                        <span
                          key={i}
                          onClick={() => setApproveEmail(e)}
                          style={{ cursor: 'pointer', color: 'var(--primary)', marginRight: '0.5rem' }}
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
    </div>
  );
}

function LeadRow({ lead, selected, onToggle, onEnrich, onApprove, onDelete, enriching, expanded, onExpand }) {
  const emails = lead.emails_found || [];
  const hasEmail = emails.length > 0;

  const scoreColor = (score) => {
    if (!score && score !== 0) return 'var(--text-light)';
    if (score >= 70) return 'var(--success)';
    if (score >= 40) return 'var(--warning)';
    return 'var(--error)';
  };

  return (
    <>
      <tr onClick={onExpand} style={{ cursor: 'pointer' }}>
        <td onClick={e => e.stopPropagation()}>
          <input type="checkbox" checked={selected} onChange={onToggle} />
        </td>
        <td>
          <div style={{ fontWeight: 500 }}>{lead.name}</div>
          <div className="text-light" style={{ fontSize: '0.6875rem', marginTop: '0.125rem' }}>
            {lead.address ? (lead.address.length > 40 ? lead.address.slice(0, 40) + '...' : lead.address) : '—'}
          </div>
        </td>
        <td>
          <span style={{ fontSize: '0.75rem' }} className="text-light">
            {lead.business_category ? lead.business_category.replace(/_/g, ' ') : '—'}
          </span>
        </td>
        <td>
          {lead.google_rating ? (
            <span style={{ color: lead.google_rating >= 4 ? 'var(--warning)' : 'var(--text-light)' }}>
              {lead.google_rating} ({lead.review_count || 0})
            </span>
          ) : '—'}
        </td>
        <td>
          {lead.employee_count ? (
            <span>
              {lead.employee_count}
              <span className="text-light" style={{ fontSize: '0.625rem', marginLeft: '0.25rem' }}>
                ({lead.employee_count_source})
              </span>
            </span>
          ) : (
            <span className="text-light">{lead.status === 'new' ? 'Pending' : '—'}</span>
          )}
        </td>
        <td>
          {hasEmail ? (
            <span style={{ color: 'var(--success)', fontSize: '0.75rem' }}>{emails[0]}</span>
          ) : (
            <span className="text-light">{lead.status === 'new' ? 'Pending' : 'None'}</span>
          )}
        </td>
        <td>
          {lead.linkedin_url ? (
            <a
              href={lead.linkedin_url}
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: 'var(--primary)', fontSize: '0.75rem' }}
              onClick={e => e.stopPropagation()}
            >
              View
            </a>
          ) : (
            <span className="text-light">—</span>
          )}
        </td>
        <td>
          {lead.score != null ? (
            <span style={{
              fontWeight: 600,
              color: scoreColor(lead.score),
              background: scoreColor(lead.score) === 'var(--success)' ? 'rgba(16,185,129,0.1)'
                : scoreColor(lead.score) === 'var(--warning)' ? 'rgba(245,158,11,0.1)'
                : scoreColor(lead.score) === 'var(--error)' ? 'rgba(239,68,68,0.1)'
                : 'transparent',
              padding: '0.125rem 0.5rem',
              borderRadius: '0.25rem',
              fontSize: '0.8125rem',
            }}>
              {lead.score}
            </span>
          ) : '—'}
        </td>
        <td>
          <span className={`badge ${STATUS_BADGE_CLASS[lead.status] || 'badge-pending'}`}>
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
                style={{ padding: '0.2rem 0.5rem', fontSize: '0.6875rem' }}
              >
                {enriching ? 'Enriching...' : 'Enrich'}
              </button>
            )}
            {['enriched', 'qualified'].includes(lead.status) && (
              <button
                className="btn btn-success btn-sm"
                onClick={onApprove}
                style={{ padding: '0.2rem 0.5rem', fontSize: '0.6875rem' }}
              >
                Approve
              </button>
            )}
            <button
              className="btn btn-danger btn-sm"
              onClick={onDelete}
              style={{ padding: '0.2rem 0.5rem', fontSize: '0.6875rem' }}
            >
              Delete
            </button>
          </div>
        </td>
      </tr>

      {/* Expanded detail row */}
      {expanded && (
        <tr>
          <td colSpan={10} style={{ padding: '0.75rem 1rem', background: 'var(--bg)' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem', fontSize: '0.8125rem' }}>
              <div>
                <h4 style={{ margin: '0 0 0.5rem', fontWeight: 500, fontSize: '0.75rem', textTransform: 'uppercase' }} className="text-light">
                  Contact Info
                </h4>
                <Detail label="Phone" value={lead.phone} />
                <Detail label="Website" value={lead.website} link />
                <Detail label="Address" value={lead.address} />
              </div>
              <div>
                <h4 style={{ margin: '0 0 0.5rem', fontWeight: 500, fontSize: '0.75rem', textTransform: 'uppercase' }} className="text-light">
                  Enrichment Data
                </h4>
                <Detail label="Employees" value={lead.employee_count ? `${lead.employee_count} (via ${lead.employee_count_source})` : null} />
                <Detail label="LinkedIn" value={lead.linkedin_url} link />
                <Detail label="Decision Maker" value={lead.decision_maker} />
                <Detail label="Year Founded" value={lead.year_founded} />
                <Detail label="Emails Found" value={emails.join(', ') || null} />
              </div>
              <div>
                <h4 style={{ margin: '0 0 0.5rem', fontWeight: 500, fontSize: '0.75rem', textTransform: 'uppercase' }} className="text-light">
                  Score Breakdown
                </h4>
                {lead.score_breakdown && Object.entries(lead.score_breakdown).map(([key, val]) => (
                  <div key={key} className="flex justify-between" style={{ marginBottom: '0.25rem' }}>
                    <span>{key.replace(/_/g, ' ')}</span>
                    <span style={{ color: 'var(--success)', fontWeight: 500 }}>+{val}</span>
                  </div>
                ))}
                {!lead.score_breakdown || Object.keys(lead.score_breakdown).length === 0 ? (
                  <span className="text-light">Not scored yet</span>
                ) : null}
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
    <div style={{ marginBottom: '0.25rem' }}>
      <span className="text-light">{label}: —</span>
    </div>
  );
  return (
    <div style={{ marginBottom: '0.25rem' }}>
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

function StatCard({ label, value, accent }) {
  return (
    <div className="card" style={{
      padding: '0.75rem 1rem',
      borderLeft: accent ? `3px solid ${accent}` : 'none',
    }}>
      <div style={{ fontSize: '0.6875rem', textTransform: 'uppercase', marginBottom: '0.25rem' }} className="text-light">{label}</div>
      <div style={{ fontSize: '1.375rem', fontWeight: 600, color: accent || 'var(--text)' }}>{value}</div>
    </div>
  );
}

export default Pipeline;
