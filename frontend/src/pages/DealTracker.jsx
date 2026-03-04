import { useState, useEffect, useCallback } from 'react';
import {
  getDeals, getDealStats, createDeal, updateDeal, deleteDeal,
  updateDealStage, getContacts,
} from '../api/client';
import { useToast } from '../components/Toast';
import ConfirmDialog from '../components/ConfirmDialog';

const STAGES = [
  { value: 'interested', label: 'Interested', color: '#6B7280' },
  { value: 'contacted_broker', label: 'Contacted Broker', color: '#3B82F6' },
  { value: 'nda_signed', label: 'NDA Signed', color: '#8B5CF6' },
  { value: 'reviewing_financials', label: 'Reviewing Financials', color: '#F59E0B' },
  { value: 'loi_submitted', label: 'LOI Submitted', color: '#E8603C' },
  { value: 'under_contract', label: 'Under Contract', color: '#D97706' },
  { value: 'due_diligence', label: 'Due Diligence', color: '#0891B2' },
  { value: 'closed_won', label: 'Closed Won', color: '#10B981' },
  { value: 'closed_lost', label: 'Closed Lost', color: '#EF4444' },
];

const STAGE_MAP = Object.fromEntries(STAGES.map(s => [s.value, s]));

function formatPrice(num) {
  if (num == null) return '--';
  if (num >= 1_000_000) return `$${(num / 1_000_000).toFixed(1)}M`;
  if (num >= 1_000) return `$${(num / 1_000).toFixed(0)}K`;
  return `$${num.toLocaleString()}`;
}

function daysAgo(isoStr) {
  if (!isoStr) return '--';
  const diff = Date.now() - new Date(isoStr).getTime();
  const days = Math.floor(diff / 86400000);
  if (days === 0) return 'Today';
  if (days === 1) return '1 day ago';
  return `${days} days ago`;
}

function DealTracker() {
  const [deals, setDeals] = useState([]);
  const [stats, setStats] = useState({});
  const [contacts, setContacts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({ stage: '' });
  const [sort, setSort] = useState({ by: 'updated_at', order: 'desc' });
  const [search, setSearch] = useState('');
  const [expandedDeal, setExpandedDeal] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [editingDeal, setEditingDeal] = useState(null);
  const [confirmState, setConfirmState] = useState(null);
  const [showFinancials, setShowFinancials] = useState(false);
  const showToast = useToast();

  const emptyForm = {
    name: '', stage: 'interested', contact_id: '',
    asking_price: '', offer_price: '', revenue: '', cash_flow: '', sde: '', ebitda: '',
    broker_name: '', broker_email: '', broker_phone: '',
    source: '', url: '', location: '', category: '', notes: '', expected_close_date: '',
  };
  const [form, setForm] = useState(emptyForm);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const params = { sort: sort.by, order: sort.order };
      if (filter.stage) params.stage = filter.stage;

      const [dealsRes, statsRes, contactsRes] = await Promise.all([
        getDeals(params),
        getDealStats(),
        getContacts({ per_page: 200 }),
      ]);
      setDeals(dealsRes.data.deals || []);
      setStats(statsRes.data);
      setContacts(contactsRes.data?.contacts || contactsRes.data || []);
    } catch (err) {
      console.error('Deal tracker load error:', err);
    }
    setLoading(false);
  }, [filter, sort]);

  useEffect(() => { loadData(); }, [loadData]);

  const filteredDeals = deals.filter(deal => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      (deal.name || '').toLowerCase().includes(q) ||
      (deal.broker_name || '').toLowerCase().includes(q) ||
      (deal.source || '').toLowerCase().includes(q) ||
      (deal.location || '').toLowerCase().includes(q) ||
      (deal.category || '').toLowerCase().includes(q)
    );
  });

  const handleStageChange = async (dealId, newStage) => {
    try {
      await updateDealStage(dealId, newStage);
      showToast('Stage updated', 'success');
      await loadData();
    } catch (err) {
      showToast('Failed to update stage', 'error');
    }
  };

  const openCreateModal = () => {
    setEditingDeal(null);
    setForm(emptyForm);
    setShowFinancials(false);
    setShowModal(true);
  };

  const openEditModal = (deal) => {
    setEditingDeal(deal);
    setForm({
      name: deal.name || '',
      stage: deal.stage || 'interested',
      contact_id: deal.contact_id || '',
      asking_price: deal.asking_price || '',
      offer_price: deal.offer_price || '',
      revenue: deal.revenue || '',
      cash_flow: deal.cash_flow || '',
      sde: deal.sde || '',
      ebitda: deal.ebitda || '',
      broker_name: deal.broker_name || '',
      broker_email: deal.broker_email || '',
      broker_phone: deal.broker_phone || '',
      source: deal.source || '',
      url: deal.url || '',
      location: deal.location || '',
      category: deal.category || '',
      notes: deal.notes || '',
      expected_close_date: deal.expected_close_date || '',
    });
    setShowFinancials(Boolean(deal.revenue || deal.cash_flow || deal.sde || deal.ebitda));
    setShowModal(true);
  };

  const handleSave = async () => {
    if (!form.name.trim()) {
      showToast('Deal name is required', 'error');
      return;
    }
    const payload = { ...form };
    // Convert numeric fields
    for (const f of ['asking_price', 'offer_price', 'revenue', 'cash_flow', 'sde', 'ebitda']) {
      payload[f] = payload[f] === '' ? null : Number(payload[f]);
    }
    payload.contact_id = payload.contact_id || null;
    payload.expected_close_date = payload.expected_close_date || null;

    try {
      if (editingDeal) {
        await updateDeal(editingDeal.id, payload);
        showToast('Deal updated', 'success');
      } else {
        await createDeal(payload);
        showToast('Deal created', 'success');
      }
      setShowModal(false);
      await loadData();
    } catch (err) {
      showToast(err.response?.data?.error || 'Failed to save deal', 'error');
    }
  };

  const handleDelete = (deal) => {
    setConfirmState({
      title: `Delete "${deal.name}"?`,
      message: 'This action cannot be undone.',
      confirmLabel: 'Delete',
      confirmClass: 'btn-danger',
      onConfirm: async () => {
        setConfirmState(null);
        try {
          await deleteDeal(deal.id);
          showToast('Deal deleted', 'info');
          await loadData();
        } catch (err) {
          showToast('Failed to delete deal', 'error');
        }
      },
    });
  };

  const activeStages = STAGES.filter(s => !['closed_won', 'closed_lost'].includes(s.value));

  if (loading) {
    return (
      <div style={{ maxWidth: 1400 }}>
        <div className="page-header">
          <div>
            <h1>Deal Tracker</h1>
            <p className="text-sm text-light">Track live deals through your acquisition pipeline</p>
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
              <div style={{ flex: 1 }}>
                <div className="skeleton skeleton-text" style={{ width: '30%' }} />
                <div className="skeleton skeleton-text-sm" />
              </div>
              <div className="skeleton skeleton-text" style={{ width: '10%' }} />
              <div className="skeleton skeleton-text" style={{ width: '8%' }} />
              <div className="skeleton skeleton-text" style={{ width: '8%' }} />
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
          <h1>Deal Tracker</h1>
          <p className="text-sm text-light">Track live deals through your acquisition pipeline</p>
        </div>
        <button className="btn btn-primary" onClick={openCreateModal}>
          New Deal
        </button>
      </div>

      {/* Stats */}
      <div className="grid mb-4" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))' }}>
        <StatCard label="Total Deals" value={stats.total || 0} />
        <StatCard label="Active" value={stats.active_count || 0} color="#3B82F6" />
        <StatCard label="Pipeline Value" value={formatPrice(stats.pipeline_value)} color="#E8603C" />
        <StatCard
          label="LOI+"
          value={(stats.by_stage?.loi_submitted || 0) + (stats.by_stage?.under_contract || 0) + (stats.by_stage?.due_diligence || 0)}
          color="#D97706"
        />
        <StatCard label="Won" value={stats.by_stage?.closed_won || 0} color="#10B981" />
        <StatCard label="Lost" value={stats.by_stage?.closed_lost || 0} color="#EF4444" />
      </div>

      {/* Search */}
      <div className="card mb-2" style={{ padding: '0.75rem 1rem' }}>
        <input
          type="text"
          className="form-input"
          placeholder="Search deals by name, broker, source, location..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{ border: 'none', padding: 0, boxShadow: 'none' }}
        />
      </div>

      {/* Filters */}
      <div className="toolbar">
        <select
          className="form-select"
          style={{ width: 'auto' }}
          value={filter.stage}
          onChange={e => setFilter(f => ({ ...f, stage: e.target.value }))}
        >
          <option value="">All Stages</option>
          {STAGES.map(s => (
            <option key={s.value} value={s.value}>{s.label}</option>
          ))}
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
          <option value="updated_at:desc">Recently Updated</option>
          <option value="created_at:desc">Newest First</option>
          <option value="created_at:asc">Oldest First</option>
          <option value="asking_price:desc">Highest Value</option>
          <option value="asking_price:asc">Lowest Value</option>
          <option value="stage_changed_at:desc">Stage Changed</option>
        </select>
      </div>

      {/* Deals table */}
      {deals.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="empty-state-icon" style={{ fontSize: '2rem' }}>&#128188;</div>
            <p>No deals yet</p>
            <p className="text-sm text-light">
              Click <strong>New Deal</strong> to start tracking a deal, or create one from the <strong>Listings</strong> page.
            </p>
            <button className="btn btn-primary mt-2" onClick={openCreateModal}>
              New Deal
            </button>
          </div>
        </div>
      ) : filteredDeals.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="empty-state-icon" style={{ fontSize: '2rem' }}>&#128269;</div>
            <p>No deals match your filters</p>
            <button
              className="btn btn-secondary mt-2"
              onClick={() => { setSearch(''); setFilter({ stage: '' }); }}
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
                <th>Deal</th>
                <th>Stage</th>
                <th>Asking Price</th>
                <th>SDE / Revenue</th>
                <th>Broker</th>
                <th>In Stage</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredDeals.map(deal => (
                <DealRow
                  key={deal.id}
                  deal={deal}
                  expanded={expandedDeal === deal.id}
                  onExpand={() => setExpandedDeal(expandedDeal === deal.id ? null : deal.id)}
                  onStageChange={handleStageChange}
                  onEdit={() => openEditModal(deal)}
                  onDelete={() => handleDelete(deal)}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create/Edit Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" style={{ maxWidth: 560 }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">{editingDeal ? 'Edit Deal' : 'New Deal'}</h3>
              <button className="modal-close" onClick={() => setShowModal(false)}>&times;</button>
            </div>
            <div className="modal-body" style={{ maxHeight: '70vh', overflowY: 'auto' }}>
              <div className="form-group">
                <label className="form-label">Deal Name *</label>
                <input
                  type="text"
                  className="form-input"
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="e.g. Joe's Plumbing - Bergen County"
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div className="form-group">
                  <label className="form-label">Stage</label>
                  <select
                    className="form-select"
                    value={form.stage}
                    onChange={e => setForm(f => ({ ...f, stage: e.target.value }))}
                  >
                    {STAGES.map(s => (
                      <option key={s.value} value={s.value}>{s.label}</option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Source</label>
                  <input
                    type="text"
                    className="form-input"
                    value={form.source}
                    onChange={e => setForm(f => ({ ...f, source: e.target.value }))}
                    placeholder="e.g. BizBuySell, broker, referral"
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div className="form-group">
                  <label className="form-label">Asking Price ($)</label>
                  <input
                    type="number"
                    className="form-input"
                    value={form.asking_price}
                    onChange={e => setForm(f => ({ ...f, asking_price: e.target.value }))}
                    placeholder="500000"
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Offer Price ($)</label>
                  <input
                    type="number"
                    className="form-input"
                    value={form.offer_price}
                    onChange={e => setForm(f => ({ ...f, offer_price: e.target.value }))}
                    placeholder="450000"
                  />
                </div>
              </div>

              {/* Financial Details Toggle */}
              <div style={{ marginBottom: '12px' }}>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => setShowFinancials(!showFinancials)}
                  style={{ fontSize: '0.75rem' }}
                >
                  {showFinancials ? 'Hide' : 'Show'} Financial Details
                </button>
              </div>

              {showFinancials && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div className="form-group">
                    <label className="form-label">Revenue ($)</label>
                    <input type="number" className="form-input" value={form.revenue}
                      onChange={e => setForm(f => ({ ...f, revenue: e.target.value }))} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Cash Flow ($)</label>
                    <input type="number" className="form-input" value={form.cash_flow}
                      onChange={e => setForm(f => ({ ...f, cash_flow: e.target.value }))} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">SDE ($)</label>
                    <input type="number" className="form-input" value={form.sde}
                      onChange={e => setForm(f => ({ ...f, sde: e.target.value }))} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">EBITDA ($)</label>
                    <input type="number" className="form-input" value={form.ebitda}
                      onChange={e => setForm(f => ({ ...f, ebitda: e.target.value }))} />
                  </div>
                </div>
              )}

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div className="form-group">
                  <label className="form-label">Location</label>
                  <input type="text" className="form-input" value={form.location}
                    onChange={e => setForm(f => ({ ...f, location: e.target.value }))}
                    placeholder="e.g. Bergen County, NJ" />
                </div>
                <div className="form-group">
                  <label className="form-label">Category</label>
                  <input type="text" className="form-input" value={form.category}
                    onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
                    placeholder="e.g. Plumbing, Restaurant" />
                </div>
              </div>

              <h4 style={{ margin: '16px 0 8px', fontSize: '0.8125rem', color: 'var(--text-light)', textTransform: 'uppercase', letterSpacing: '0.03em' }}>
                Broker Info
              </h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div className="form-group">
                  <label className="form-label">Broker Name</label>
                  <input type="text" className="form-input" value={form.broker_name}
                    onChange={e => setForm(f => ({ ...f, broker_name: e.target.value }))} />
                </div>
                <div className="form-group">
                  <label className="form-label">Broker Email</label>
                  <input type="email" className="form-input" value={form.broker_email}
                    onChange={e => setForm(f => ({ ...f, broker_email: e.target.value }))} />
                </div>
                <div className="form-group">
                  <label className="form-label">Broker Phone</label>
                  <input type="text" className="form-input" value={form.broker_phone}
                    onChange={e => setForm(f => ({ ...f, broker_phone: e.target.value }))} />
                </div>
                <div className="form-group">
                  <label className="form-label">Expected Close Date</label>
                  <input type="date" className="form-input" value={form.expected_close_date}
                    onChange={e => setForm(f => ({ ...f, expected_close_date: e.target.value }))} />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Linked Contact</label>
                <select
                  className="form-select"
                  value={form.contact_id}
                  onChange={e => setForm(f => ({ ...f, contact_id: e.target.value }))}
                >
                  <option value="">None</option>
                  {contacts.map(c => (
                    <option key={c.id} value={c.id}>
                      {c.name || c.email} {c.company ? `(${c.company})` : ''}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">URL</label>
                <input type="url" className="form-input" value={form.url}
                  onChange={e => setForm(f => ({ ...f, url: e.target.value }))}
                  placeholder="https://..." />
              </div>

              <div className="form-group">
                <label className="form-label">Notes</label>
                <textarea
                  className="form-input"
                  rows={3}
                  value={form.notes}
                  onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
                  placeholder="Add notes about this deal..."
                  style={{ resize: 'vertical' }}
                />
              </div>
            </div>

            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowModal(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleSave}>
                {editingDeal ? 'Save Changes' : 'Create Deal'}
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

function DealRow({ deal, expanded, onExpand, onStageChange, onEdit, onDelete }) {
  const stage = STAGE_MAP[deal.stage] || { label: deal.stage, color: '#6B7280' };

  return (
    <>
      <tr style={{ cursor: 'pointer' }} onClick={onExpand}>
        <td>
          <div style={{ fontWeight: 500 }}>{deal.name}</div>
          <div className="text-sm text-light" style={{ marginTop: 2 }}>
            {[deal.location, deal.category].filter(Boolean).join(' · ') || ''}
          </div>
          {deal.listing_name && (
            <span className="badge" style={{ marginTop: 4, display: 'inline-block', fontSize: '0.6875rem', background: '#DBEAFE', color: '#1E40AF' }}>
              From listing
            </span>
          )}
        </td>
        <td onClick={e => e.stopPropagation()}>
          <select
            className="form-select"
            value={deal.stage}
            onChange={e => onStageChange(deal.id, e.target.value)}
            style={{
              width: 'auto',
              fontSize: '0.75rem',
              padding: '2px 24px 2px 8px',
              color: stage.color,
              fontWeight: 600,
              border: `1px solid ${stage.color}30`,
              background: `${stage.color}10`,
              borderRadius: 4,
            }}
          >
            {STAGES.map(s => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </td>
        <td>
          <span style={{ fontWeight: 500 }}>
            {formatPrice(deal.asking_price)}
          </span>
          {deal.offer_price != null && (
            <div className="text-sm text-light" style={{ marginTop: 2 }}>
              Offer: {formatPrice(deal.offer_price)}
            </div>
          )}
        </td>
        <td>
          {deal.sde != null || deal.revenue != null ? (
            <div>
              {deal.sde != null && <div className="text-sm">SDE: {formatPrice(deal.sde)}</div>}
              {deal.revenue != null && <div className="text-sm text-light">Rev: {formatPrice(deal.revenue)}</div>}
            </div>
          ) : <span className="text-light">--</span>}
        </td>
        <td>
          {deal.broker_name ? (
            <span className="text-sm">{deal.broker_name}</span>
          ) : <span className="text-light">--</span>}
        </td>
        <td>
          <span className="text-sm text-light">{daysAgo(deal.stage_changed_at)}</span>
        </td>
        <td onClick={e => e.stopPropagation()}>
          <div className="flex gap-1">
            <button className="btn btn-secondary btn-sm" onClick={onEdit}>Edit</button>
            <button className="btn btn-danger btn-sm" onClick={onDelete}>Delete</button>
          </div>
        </td>
      </tr>

      {/* Expanded detail */}
      {expanded && (
        <tr>
          <td colSpan={7} style={{ background: 'var(--bg)', padding: 0 }}>
            <div style={{ padding: '1rem 1.5rem' }}>
              <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
                <div>
                  <SectionTitle>Financial Details</SectionTitle>
                  <Detail label="Asking Price" value={formatPrice(deal.asking_price)} />
                  <Detail label="Offer Price" value={formatPrice(deal.offer_price)} />
                  <Detail label="Revenue" value={formatPrice(deal.revenue)} />
                  <Detail label="Cash Flow" value={formatPrice(deal.cash_flow)} />
                  <Detail label="SDE" value={formatPrice(deal.sde)} />
                  <Detail label="EBITDA" value={formatPrice(deal.ebitda)} />
                  {deal.asking_price && deal.sde ? (
                    <Detail label="Multiple" value={`${(deal.asking_price / deal.sde).toFixed(1)}x SDE`} />
                  ) : null}
                </div>
                <div>
                  <SectionTitle>Broker Info</SectionTitle>
                  <Detail label="Name" value={deal.broker_name} />
                  <Detail label="Email" value={deal.broker_email} />
                  <Detail label="Phone" value={deal.broker_phone} />
                  <Detail label="Source" value={deal.source} />
                  {deal.url && (
                    <div style={{ marginBottom: 4 }} className="text-sm">
                      <span className="text-light">URL: </span>
                      <a href={deal.url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--primary)' }}>
                        {deal.url.length > 50 ? deal.url.slice(0, 50) + '...' : deal.url}
                      </a>
                    </div>
                  )}
                </div>
                <div>
                  <SectionTitle>Linked Records</SectionTitle>
                  {deal.listing_name ? (
                    <Detail label="Listing" value={deal.listing_name} />
                  ) : (
                    <Detail label="Listing" value={null} />
                  )}
                  {deal.contact_name ? (
                    <div style={{ marginBottom: 4 }} className="text-sm">
                      <span className="text-light">Contact: </span>
                      <a href={`/contacts/${deal.contact_id}`} style={{ color: 'var(--primary)' }}>
                        {deal.contact_name}
                      </a>
                      {deal.contact_email && <span className="text-light"> ({deal.contact_email})</span>}
                    </div>
                  ) : (
                    <Detail label="Contact" value={null} />
                  )}
                  <Detail label="Location" value={deal.location} />
                  <Detail label="Category" value={deal.category} />
                </div>
                <div>
                  <SectionTitle>Dates & Notes</SectionTitle>
                  <Detail label="Created" value={deal.created_at ? new Date(deal.created_at).toLocaleDateString() : null} />
                  <Detail label="Last Updated" value={deal.updated_at ? new Date(deal.updated_at).toLocaleDateString() : null} />
                  <Detail label="Stage Changed" value={deal.stage_changed_at ? new Date(deal.stage_changed_at).toLocaleDateString() : null} />
                  <Detail label="Expected Close" value={deal.expected_close_date || null} />
                  {deal.notes && (
                    <div style={{ marginTop: 8 }}>
                      <div className="text-sm text-light" style={{ marginBottom: 4 }}>Notes:</div>
                      <div className="text-sm" style={{ whiteSpace: 'pre-wrap', background: 'var(--card-bg)', padding: '8px 12px', borderRadius: 6, border: '1px solid var(--border)' }}>
                        {deal.notes}
                      </div>
                    </div>
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

function SectionTitle({ children }) {
  return (
    <h4 className="text-light" style={{ margin: '0 0 8px', fontWeight: 500, fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.03em' }}>
      {children}
    </h4>
  );
}

function Detail({ label, value }) {
  return (
    <div style={{ marginBottom: 4 }} className="text-sm">
      <span className="text-light">{label}: </span>
      <span>{value || '--'}</span>
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

export default DealTracker;
