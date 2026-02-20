import { useState, useEffect, useCallback } from 'react';
import {
  getPipelineLeads, getPipelineStats, enrichPipelineLead, bulkEnrichLeads,
  approvePipelineLead, bulkApproveLeads, bulkRejectLeads, deletePipelineLead,
  getCampaigns,
} from '../api/client';

const STATUS_COLORS = {
  new: '#6B7280',
  enriching: '#F59E0B',
  enriched: '#3B82F6',
  qualified: '#8B5CF6',
  approved: '#10B981',
  in_campaign: '#059669',
  rejected: '#EF4444',
};

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
  const [approveModal, setApproveModal] = useState(null); // lead object or 'bulk'
  const [approveEmail, setApproveEmail] = useState('');
  const [approveCampaignId, setApproveCampaignId] = useState('');
  const [expandedLead, setExpandedLead] = useState(null);

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

  const scoreColor = (score) => {
    if (!score && score !== 0) return '#6B7280';
    if (score >= 70) return '#10B981';
    if (score >= 40) return '#F59E0B';
    return '#EF4444';
  };

  const retirementColor = (label) => {
    if (label === 'high') return '#F59E0B';
    if (label === 'medium') return '#3B82F6';
    return '#6B7280';
  };

  if (loading) {
    return (
      <div style={{ padding: 32 }}>
        <h1 style={{ fontSize: 24, fontWeight: 600, marginBottom: 8 }}>Lead Pipeline</h1>
        <p style={{ color: '#9CA3AF' }}>Loading...</p>
      </div>
    );
  }

  return (
    <div style={{ padding: 32, maxWidth: 1400 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 600, margin: 0 }}>Lead Pipeline</h1>
          <p style={{ color: '#9CA3AF', margin: '4px 0 0' }}>
            Discover, enrich, and qualify leads before outbound
          </p>
        </div>
      </div>

      {/* Stats cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12, marginBottom: 24 }}>
        <StatCard label="Total Leads" value={stats.total || 0} />
        <StatCard label="New" value={stats.by_status?.new || 0} color="#6B7280" />
        <StatCard label="Enriched" value={(stats.by_status?.enriched || 0) + (stats.by_status?.qualified || 0)} color="#3B82F6" />
        <StatCard label="Qualified" value={stats.by_status?.qualified || 0} color="#8B5CF6" />
        <StatCard label="Approved" value={(stats.by_status?.approved || 0) + (stats.by_status?.in_campaign || 0)} color="#10B981" />
        <StatCard label="Avg Score" value={stats.avg_score || 0} />
        <StatCard label="Has Email" value={stats.with_email || 0} color="#059669" />
        <StatCard label="Has Employee #" value={stats.with_employee_count || 0} color="#7C3AED" />
        <StatCard label="Likely Retiring" value={stats.with_high_retirement || 0} color="#F59E0B" />
      </div>

      {/* Filters and bulk actions */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        <select
          value={filter.status}
          onChange={e => setFilter(f => ({ ...f, status: e.target.value }))}
          style={selectStyle}
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
          value={filter.min_score}
          onChange={e => setFilter(f => ({ ...f, min_score: e.target.value }))}
          style={selectStyle}
        >
          <option value="">Any Score</option>
          <option value="30">30+</option>
          <option value="50">50+</option>
          <option value="60">60+ (Qualified)</option>
          <option value="70">70+</option>
          <option value="80">80+</option>
        </select>

        <select
          value={filter.retirement_label}
          onChange={e => setFilter(f => ({ ...f, retirement_label: e.target.value }))}
          style={selectStyle}
        >
          <option value="">Any Retirement</option>
          <option value="high">Likely Retiring</option>
          <option value="medium">Maybe Retiring</option>
          <option value="low">Unlikely</option>
        </select>

        <select
          value={`${sort.by}:${sort.order}`}
          onChange={e => {
            const [by, order] = e.target.value.split(':');
            setSort({ by, order });
          }}
          style={selectStyle}
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

        <div style={{ flex: 1 }} />

        {selected.size > 0 && (
          <>
            <span style={{ color: '#9CA3AF', fontSize: 13 }}>{selected.size} selected</span>
            <button onClick={handleBulkEnrich} style={btnStyle('#3B82F6')}>
              Enrich Selected
            </button>
            <button onClick={openBulkApproveModal} style={btnStyle('#10B981')}>
              Approve Selected
            </button>
            <button onClick={handleBulkReject} style={btnStyle('#EF4444')}>
              Reject
            </button>
          </>
        )}
      </div>

      {/* Leads table */}
      {leads.length === 0 ? (
        <div style={{ padding: 48, textAlign: 'center', color: '#9CA3AF', background: '#1F2937', borderRadius: 8 }}>
          <p style={{ fontSize: 16, marginBottom: 8 }}>No leads in your pipeline yet</p>
          <p style={{ fontSize: 13 }}>
            Go to <strong>Map Explorer</strong> and click "Add to Pipeline" on businesses you want to prospect.
          </p>
        </div>
      ) : (
        <div style={{ background: '#1F2937', borderRadius: 8, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #374151' }}>
                <th style={thStyle}>
                  <input
                    type="checkbox"
                    checked={selected.size === leads.length && leads.length > 0}
                    onChange={toggleSelectAll}
                  />
                </th>
                <th style={thStyle}>Business</th>
                <th style={thStyle}>Category</th>
                <th style={thStyle}>Rating</th>
                <th style={thStyle}>Employees</th>
                <th style={thStyle}>Email</th>
                <th style={thStyle}>LinkedIn</th>
                <th style={thStyle}>Score</th>
                <th style={thStyle}>Retirement</th>
                <th style={thStyle}>Status</th>
                <th style={thStyle}>Actions</th>
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
        <div style={overlayStyle} onClick={() => setApproveModal(null)}>
          <div style={modalStyle} onClick={e => e.stopPropagation()}>
            <h3 style={{ margin: '0 0 16px', fontSize: 18 }}>
              {approveModal === 'bulk'
                ? `Approve ${selected.size} Leads`
                : `Approve: ${approveModal.name}`}
            </h3>

            {approveModal !== 'bulk' && (
              <div style={{ marginBottom: 12 }}>
                <label style={labelStyle}>Email Address *</label>
                <input
                  type="email"
                  value={approveEmail}
                  onChange={e => setApproveEmail(e.target.value)}
                  placeholder="contact@business.com"
                  style={inputStyle}
                />
                {approveModal.emails_found?.length > 0 && (
                  <div style={{ marginTop: 4, fontSize: 12, color: '#9CA3AF' }}>
                    Found: {approveModal.emails_found.map((e, i) => (
                      <span
                        key={i}
                        onClick={() => setApproveEmail(e)}
                        style={{ cursor: 'pointer', color: '#60A5FA', marginRight: 8 }}
                      >
                        {e}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div style={{ marginBottom: 16 }}>
              <label style={labelStyle}>Add to Campaign (optional)</label>
              <select
                value={approveCampaignId}
                onChange={e => setApproveCampaignId(e.target.value)}
                style={inputStyle}
              >
                <option value="">Don't add to campaign</option>
                {campaigns.map(c => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.status})
                  </option>
                ))}
              </select>
            </div>

            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button onClick={() => setApproveModal(null)} style={btnStyle('#374151')}>
                Cancel
              </button>
              <button onClick={handleApprove} style={btnStyle('#10B981')}>
                Approve & Create Contact
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function LeadRow({ lead, selected, onToggle, onEnrich, onApprove, onDelete, enriching, expanded, onExpand, scoreColor, retirementColor }) {
  const emails = lead.emails_found || [];
  const hasEmail = emails.length > 0;

  return (
    <>
      <tr
        style={{ borderBottom: '1px solid #374151', cursor: 'pointer' }}
        onClick={onExpand}
      >
        <td style={tdStyle} onClick={e => e.stopPropagation()}>
          <input type="checkbox" checked={selected} onChange={onToggle} />
        </td>
        <td style={tdStyle}>
          <div style={{ fontWeight: 500, color: '#F3F4F6' }}>{lead.name}</div>
          <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 2 }}>
            {lead.address ? (lead.address.length > 40 ? lead.address.slice(0, 40) + '...' : lead.address) : '—'}
          </div>
        </td>
        <td style={tdStyle}>
          <span style={{ fontSize: 12, color: '#D1D5DB' }}>
            {lead.business_category ? lead.business_category.replace(/_/g, ' ') : '—'}
          </span>
        </td>
        <td style={tdStyle}>
          {lead.google_rating ? (
            <span style={{ color: lead.google_rating >= 4 ? '#FBBF24' : '#D1D5DB' }}>
              {lead.google_rating} ({lead.review_count || 0})
            </span>
          ) : '—'}
        </td>
        <td style={tdStyle}>
          {lead.employee_count ? (
            <span>
              {lead.employee_count}
              <span style={{ fontSize: 10, color: '#9CA3AF', marginLeft: 4 }}>
                ({lead.employee_count_source})
              </span>
            </span>
          ) : (
            <span style={{ color: '#6B7280' }}>{lead.status === 'new' ? 'Pending' : '—'}</span>
          )}
        </td>
        <td style={tdStyle}>
          {hasEmail ? (
            <span style={{ color: '#34D399', fontSize: 12 }}>{emails[0]}</span>
          ) : (
            <span style={{ color: '#6B7280' }}>{lead.status === 'new' ? 'Pending' : 'None'}</span>
          )}
        </td>
        <td style={tdStyle}>
          {lead.linkedin_url ? (
            <a
              href={lead.linkedin_url}
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: '#60A5FA', fontSize: 12 }}
              onClick={e => e.stopPropagation()}
            >
              View
            </a>
          ) : (
            <span style={{ color: '#6B7280' }}>—</span>
          )}
        </td>
        <td style={tdStyle}>
          {lead.score != null ? (
            <span style={{
              fontWeight: 600,
              color: scoreColor(lead.score),
              background: scoreColor(lead.score) + '20',
              padding: '2px 8px',
              borderRadius: 4,
              fontSize: 13,
            }}>
              {lead.score}
            </span>
          ) : '—'}
        </td>
        <td style={tdStyle}>
          {lead.retirement_score != null ? (
            <span style={{
              fontWeight: 600,
              color: retirementColor(lead.retirement_label),
              background: retirementColor(lead.retirement_label) + '20',
              padding: '2px 8px',
              borderRadius: 4,
              fontSize: 12,
            }}>
              {lead.retirement_label === 'high' ? 'Likely' :
               lead.retirement_label === 'medium' ? 'Maybe' :
               lead.retirement_label === 'low' ? 'Unlikely' : '?'}
              <span style={{ fontSize: 10, marginLeft: 4, opacity: 0.7 }}>
                {lead.retirement_score}
              </span>
            </span>
          ) : (
            <span style={{ color: '#6B7280' }}>{lead.status === 'new' ? '' : '—'}</span>
          )}
        </td>
        <td style={tdStyle}>
          <span style={{
            fontSize: 11,
            padding: '2px 8px',
            borderRadius: 4,
            background: (STATUS_COLORS[lead.status] || '#6B7280') + '20',
            color: STATUS_COLORS[lead.status] || '#6B7280',
            fontWeight: 500,
          }}>
            {STATUS_LABELS[lead.status] || lead.status}
          </span>
        </td>
        <td style={tdStyle} onClick={e => e.stopPropagation()}>
          <div style={{ display: 'flex', gap: 4 }}>
            {['new', 'enriched'].includes(lead.status) && (
              <button
                onClick={onEnrich}
                disabled={enriching}
                style={{ ...smallBtn, background: '#1E40AF', opacity: enriching ? 0.5 : 1 }}
              >
                {enriching ? '...' : 'Enrich'}
              </button>
            )}
            {['enriched', 'qualified'].includes(lead.status) && (
              <button onClick={onApprove} style={{ ...smallBtn, background: '#065F46' }}>
                Approve
              </button>
            )}
            <button onClick={onDelete} style={{ ...smallBtn, background: '#7F1D1D' }}>
              X
            </button>
          </div>
        </td>
      </tr>

      {/* Expanded detail row */}
      {expanded && (
        <tr style={{ background: '#111827' }}>
          <td colSpan={11} style={{ padding: '12px 16px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 16, fontSize: 13 }}>
              <div>
                <h4 style={{ margin: '0 0 8px', color: '#9CA3AF', fontWeight: 500, fontSize: 12, textTransform: 'uppercase' }}>
                  Contact Info
                </h4>
                <Detail label="Phone" value={lead.phone} />
                <Detail label="Website" value={lead.website} link />
                <Detail label="Address" value={lead.address} />
              </div>
              <div>
                <h4 style={{ margin: '0 0 8px', color: '#9CA3AF', fontWeight: 500, fontSize: 12, textTransform: 'uppercase' }}>
                  Enrichment Data
                </h4>
                <Detail label="Employees" value={lead.employee_count ? `${lead.employee_count} (via ${lead.employee_count_source})` : null} />
                <Detail label="LinkedIn" value={lead.linkedin_url} link />
                <Detail label="Decision Maker" value={lead.decision_maker} />
                <Detail label="Year Founded" value={lead.year_founded} />
                <Detail label="Emails Found" value={emails.join(', ') || null} />
              </div>
              <div>
                <h4 style={{ margin: '0 0 8px', color: '#9CA3AF', fontWeight: 500, fontSize: 12, textTransform: 'uppercase' }}>
                  Score Breakdown
                </h4>
                {lead.score_breakdown && Object.entries(lead.score_breakdown).map(([key, val]) => (
                  <div key={key} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ color: '#D1D5DB' }}>{key.replace(/_/g, ' ')}</span>
                    <span style={{ color: '#10B981' }}>+{val}</span>
                  </div>
                ))}
                {!lead.score_breakdown || Object.keys(lead.score_breakdown).length === 0 ? (
                  <span style={{ color: '#6B7280' }}>Not scored yet</span>
                ) : null}
              </div>
              <div>
                <h4 style={{ margin: '0 0 8px', color: '#9CA3AF', fontWeight: 500, fontSize: 12, textTransform: 'uppercase' }}>
                  Retirement Signals
                </h4>
                {lead.retirement_score != null ? (
                  <>
                    <Detail label="Score" value={`${lead.retirement_score}/100 (${lead.retirement_label})`} />
                    {lead.enrichment_data?.retirement_signals?.analysis?.key_evidence?.map((ev, i) => (
                      <div key={i} style={{ marginBottom: 4 }}>
                        <span style={{ color: '#9CA3AF', fontSize: 11 }}>Signal: </span>
                        <span style={{ color: '#F3F4F6', fontSize: 12 }}>{ev}</span>
                      </div>
                    ))}
                    {(!lead.enrichment_data?.retirement_signals?.analysis?.key_evidence?.length) && (
                      <span style={{ color: '#6B7280', fontSize: 12 }}>No specific signals found</span>
                    )}
                  </>
                ) : (
                  <span style={{ color: '#6B7280' }}>Not assessed yet</span>
                )}
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
    <div style={{ marginBottom: 4 }}>
      <span style={{ color: '#6B7280' }}>{label}: —</span>
    </div>
  );
  return (
    <div style={{ marginBottom: 4 }}>
      <span style={{ color: '#9CA3AF' }}>{label}: </span>
      {link ? (
        <a href={value.startsWith('http') ? value : `https://${value}`} target="_blank" rel="noopener noreferrer" style={{ color: '#60A5FA' }}>
          {value.length > 40 ? value.slice(0, 40) + '...' : value}
        </a>
      ) : (
        <span style={{ color: '#F3F4F6' }}>{value}</span>
      )}
    </div>
  );
}

function StatCard({ label, value, color }) {
  return (
    <div style={{
      background: '#1F2937',
      borderRadius: 8,
      padding: '12px 16px',
      borderLeft: color ? `3px solid ${color}` : 'none',
    }}>
      <div style={{ fontSize: 11, color: '#9CA3AF', textTransform: 'uppercase', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 600, color: color || '#F3F4F6' }}>{value}</div>
    </div>
  );
}

// Styles
const thStyle = {
  padding: '10px 12px',
  textAlign: 'left',
  fontSize: 11,
  color: '#9CA3AF',
  fontWeight: 500,
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
};

const tdStyle = {
  padding: '10px 12px',
  color: '#D1D5DB',
};

const selectStyle = {
  background: '#1F2937',
  color: '#D1D5DB',
  border: '1px solid #374151',
  borderRadius: 6,
  padding: '6px 12px',
  fontSize: 13,
};

const btnStyle = (bg) => ({
  background: bg,
  color: '#fff',
  border: 'none',
  borderRadius: 6,
  padding: '6px 14px',
  fontSize: 13,
  cursor: 'pointer',
  fontWeight: 500,
});

const smallBtn = {
  color: '#fff',
  border: 'none',
  borderRadius: 4,
  padding: '3px 8px',
  fontSize: 11,
  cursor: 'pointer',
};

const overlayStyle = {
  position: 'fixed',
  top: 0, left: 0, right: 0, bottom: 0,
  background: 'rgba(0,0,0,0.6)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 1000,
};

const modalStyle = {
  background: '#1F2937',
  borderRadius: 12,
  padding: 24,
  width: 440,
  maxWidth: '90vw',
};

const labelStyle = {
  display: 'block',
  fontSize: 12,
  color: '#9CA3AF',
  marginBottom: 4,
  fontWeight: 500,
};

const inputStyle = {
  width: '100%',
  background: '#111827',
  color: '#F3F4F6',
  border: '1px solid #374151',
  borderRadius: 6,
  padding: '8px 12px',
  fontSize: 14,
  boxSizing: 'border-box',
};

export default Pipeline;
