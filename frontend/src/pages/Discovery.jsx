import { useState, useEffect } from 'react';
import {
  getDiscoveryCriteria, createDiscoveryCriteria, updateDiscoveryCriteria,
  deleteDiscoveryCriteria, triggerDiscoveryScan, getProspects,
  qualifyProspect, addProspectToCampaign, bulkAddProspects, dismissProspect,
  getDiscoveryStats, getCampaigns,
} from '../api/client';

function Discovery() {
  const [criteria, setCriteria] = useState([]);
  const [prospects, setProspects] = useState([]);
  const [stats, setStats] = useState({});
  const [campaigns, setCampaigns] = useState([]);
  const [selectedProspects, setSelectedProspects] = useState(new Set());
  const [showCriteriaForm, setShowCriteriaForm] = useState(false);
  const [showCampaignPicker, setShowCampaignPicker] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({ min_rating: '', category: '' });
  const [dismissingId, setDismissingId] = useState(null);
  const [qualifyingId, setQualifyingId] = useState(null);
  const [confirmDismiss, setConfirmDismiss] = useState(null);

  // New criteria form state
  const [newCriteria, setNewCriteria] = useState({
    name: '', search_queries: '', zip_codes: '', min_rating: 0,
    max_results_per_query: 20, scan_interval_hours: 168,
  });

  useEffect(() => { loadAll(); }, []);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [criteriaRes, prospectsRes, statsRes, campaignsRes] = await Promise.all([
        getDiscoveryCriteria(),
        getProspects(filter),
        getDiscoveryStats(),
        getCampaigns(),
      ]);
      setCriteria(criteriaRes.data);
      setProspects(prospectsRes.data.prospects || []);
      setStats(statsRes.data);
      setCampaigns(campaignsRes.data || []);
    } catch (err) {
      console.error('Load error:', err);
    }
    setLoading(false);
  };

  const applyFilters = async () => {
    setLoading(true);
    try {
      const prospectsRes = await getProspects(filter);
      setProspects(prospectsRes.data.prospects || []);
    } catch (err) {
      console.error('Filter error:', err);
    }
    setLoading(false);
  };

  const handleCreateCriteria = async () => {
    try {
      await createDiscoveryCriteria({
        ...newCriteria,
        search_queries: newCriteria.search_queries.split(',').map(s => s.trim()).filter(Boolean),
        zip_codes: newCriteria.zip_codes.split(',').map(s => s.trim()).filter(Boolean),
      });
      setShowCriteriaForm(false);
      setNewCriteria({ name: '', search_queries: '', zip_codes: '', min_rating: 0, max_results_per_query: 20, scan_interval_hours: 168 });
      loadAll();
    } catch (err) {
      alert('Failed to create criteria: ' + (err.response?.data?.error || err.message));
    }
  };

  const handleScanNow = async (criteriaId) => {
    setScanning(true);
    try {
      await triggerDiscoveryScan(criteriaId ? { criteria_id: criteriaId } : {});
      alert('Discovery scan started in background. Results will appear shortly.');
    } catch (err) {
      alert('Scan failed: ' + (err.response?.data?.error || err.message));
    }
    setScanning(false);
  };

  const handleQualify = async (id, qualified) => {
    setQualifyingId(id);
    try {
      await qualifyProspect(id, { qualified });
      await loadAll();
    } catch (err) {
      alert('Failed to update prospect: ' + (err.response?.data?.error || err.message));
    }
    setQualifyingId(null);
  };

  const handleAddToCampaign = async (prospectId, campaignId) => {
    try {
      await addProspectToCampaign(prospectId, { campaign_id: campaignId });
      setShowCampaignPicker(null);
      loadAll();
    } catch (err) {
      alert('Failed to add to campaign: ' + (err.response?.data?.error || err.message));
    }
  };

  const handleBulkAdd = async (campaignId) => {
    try {
      await bulkAddProspects({ contact_ids: [...selectedProspects], campaign_id: campaignId });
      setSelectedProspects(new Set());
      setShowCampaignPicker(null);
      loadAll();
    } catch (err) {
      alert('Failed to add prospects: ' + (err.response?.data?.error || err.message));
    }
  };

  const handleDismiss = async (id) => {
    setDismissingId(id);
    try {
      await dismissProspect(id);
      setConfirmDismiss(null);
      await loadAll();
    } catch (err) {
      alert('Failed to dismiss prospect: ' + (err.response?.data?.error || err.message));
    }
    setDismissingId(null);
  };

  const handleDeleteCriteria = async (id) => {
    if (!confirm('Delete this search criteria?')) return;
    try {
      await deleteDiscoveryCriteria(id);
      loadAll();
    } catch (err) {
      alert('Failed to delete criteria: ' + (err.response?.data?.error || err.message));
    }
  };

  const toggleSelect = (id) => {
    const next = new Set(selectedProspects);
    next.has(id) ? next.delete(id) : next.add(id);
    setSelectedProspects(next);
  };

  const renderStars = (rating) => {
    if (!rating) return '-';
    const full = Math.floor(rating);
    return '★'.repeat(full) + (rating % 1 >= 0.5 ? '½' : '') + ` ${rating}`;
  };

  // Get unique categories for filter dropdown
  const categories = [...new Set(prospects.map(p => p.business_category).filter(Boolean))];

  return (
    <div className="page">
      <div className="page-header">
        <h1>Discovery</h1>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="btn btn-secondary" onClick={() => setShowCriteriaForm(!showCriteriaForm)}>
            + New Search
          </button>
          <button className="btn btn-primary" onClick={() => handleScanNow()} disabled={scanning}>
            {scanning ? 'Scanning...' : 'Scan All Now'}
          </button>
        </div>
      </div>

      {/* Stats */}
      <div style={{ display: 'flex', gap: '16px', marginBottom: '20px' }}>
        <div className="stat-card">
          <div className="stat-value">{stats.total || 0}</div>
          <div className="stat-label">Total Discovered</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.qualified || 0}</div>
          <div className="stat-label">Qualified</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.active_criteria || 0}</div>
          <div className="stat-label">Active Searches</div>
        </div>
      </div>

      {/* New Criteria Form */}
      {showCriteriaForm && (
        <div className="card" style={{ marginBottom: '20px', padding: '16px' }}>
          <h3>New Search Criteria</h3>
          <div className="form-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div>
              <label className="form-label">Name</label>
              <input value={newCriteria.name} onChange={e => setNewCriteria({...newCriteria, name: e.target.value})}
                placeholder="e.g. NJ Plumbers" className="form-input" />
            </div>
            <div>
              <label className="form-label">Industries (comma-separated)</label>
              <input value={newCriteria.search_queries} onChange={e => setNewCriteria({...newCriteria, search_queries: e.target.value})}
                placeholder="plumber, plumbing company" className="form-input" />
            </div>
            <div>
              <label className="form-label">Zip Codes (comma-separated)</label>
              <input value={newCriteria.zip_codes} onChange={e => setNewCriteria({...newCriteria, zip_codes: e.target.value})}
                placeholder="07302, 07304" className="form-input" />
            </div>
            <div>
              <label className="form-label">Min Rating</label>
              <input type="number" min="0" max="5" step="0.5" value={newCriteria.min_rating}
                onChange={e => setNewCriteria({...newCriteria, min_rating: parseFloat(e.target.value) || 0})}
                className="form-input" />
            </div>
            <div>
              <label className="form-label">Max Results Per Query</label>
              <input type="number" min="5" max="100" value={newCriteria.max_results_per_query}
                onChange={e => setNewCriteria({...newCriteria, max_results_per_query: parseInt(e.target.value) || 20})}
                className="form-input" />
            </div>
            <div>
              <label className="form-label">Scan Interval (hours)</label>
              <input type="number" min="24" value={newCriteria.scan_interval_hours}
                onChange={e => setNewCriteria({...newCriteria, scan_interval_hours: parseInt(e.target.value) || 168})}
                className="form-input" />
            </div>
          </div>
          <div style={{ marginTop: '12px', display: 'flex', gap: '8px' }}>
            <button className="btn btn-primary" onClick={handleCreateCriteria}>Create</button>
            <button className="btn btn-secondary" onClick={() => setShowCriteriaForm(false)}>Cancel</button>
          </div>
        </div>
      )}

      {/* Active Criteria */}
      {criteria.length > 0 && (
        <div className="card" style={{ marginBottom: '20px', padding: '16px' }}>
          <h3>Search Criteria</h3>
          <div className="criteria-list">
            {criteria.map(c => (
              <div key={c.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
                <div>
                  <strong>{c.name}</strong>
                  <span style={{ marginLeft: '12px', color: '#6B7280', fontSize: '0.9em' }}>
                    {(c.search_queries || []).join(', ')} | {(c.zip_codes || []).join(', ')}
                  </span>
                  {c.last_scanned_at && (
                    <span style={{ marginLeft: '12px', color: '#9CA3AF', fontSize: '0.85em' }}>
                      Last scan: {new Date(c.last_scanned_at).toLocaleDateString()}
                    </span>
                  )}
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button className="btn btn-sm btn-secondary" onClick={() => handleScanNow(c.id)} disabled={scanning}>Scan</button>
                  <button className="btn btn-sm btn-danger" onClick={() => handleDeleteCriteria(c.id)}>Delete</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Bulk Actions */}
      {selectedProspects.size > 0 && (
        <div className="card" style={{ marginBottom: '12px', padding: '12px', display: 'flex', alignItems: 'center', gap: '12px', background: '#EFF6FF' }}>
          <span>{selectedProspects.size} selected</span>
          <button className="btn btn-primary btn-sm" onClick={() => setShowCampaignPicker('bulk')}>
            Add to Campaign
          </button>
          <button className="btn btn-secondary btn-sm" onClick={() => setSelectedProspects(new Set())}>
            Clear
          </button>
        </div>
      )}

      {/* Prospects Table */}
      <div className="card" style={{ padding: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <h3 style={{ margin: 0 }}>Discovered Prospects ({prospects.length})</h3>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <select
              className="form-select"
              style={{ width: 'auto', minWidth: '140px', padding: '0.375rem 0.75rem', fontSize: '0.8125rem' }}
              value={filter.category}
              onChange={e => setFilter({ ...filter, category: e.target.value })}
            >
              <option value="">All Categories</option>
              {categories.map(cat => (
                <option key={cat} value={cat}>{cat}</option>
              ))}
            </select>
            <select
              className="form-select"
              style={{ width: 'auto', minWidth: '120px', padding: '0.375rem 0.75rem', fontSize: '0.8125rem' }}
              value={filter.min_rating}
              onChange={e => setFilter({ ...filter, min_rating: e.target.value })}
            >
              <option value="">Any Rating</option>
              <option value="3">3+ Stars</option>
              <option value="3.5">3.5+ Stars</option>
              <option value="4">4+ Stars</option>
              <option value="4.5">4.5+ Stars</option>
            </select>
            <button className="btn btn-sm btn-secondary" onClick={applyFilters}>Filter</button>
          </div>
        </div>
        {loading ? (
          <p>Loading...</p>
        ) : prospects.length === 0 ? (
          <p style={{ color: '#6B7280' }}>No prospects discovered yet. Create search criteria and run a scan.</p>
        ) : (
          <div className="table-container" style={{ overflowX: 'auto' }}>
            <table className="table">
              <thead>
                <tr>
                  <th style={{ width: '40px' }}><input type="checkbox" onChange={(e) => {
                    if (e.target.checked) setSelectedProspects(new Set(prospects.map(p => p.id)));
                    else setSelectedProspects(new Set());
                  }} /></th>
                  <th>Business</th>
                  <th>Category</th>
                  <th>Rating</th>
                  <th>Reviews</th>
                  <th>Contact</th>
                  <th style={{ minWidth: '180px' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {prospects.map(p => (
                  <tr key={p.id}>
                    <td><input type="checkbox" checked={selectedProspects.has(p.id)}
                      onChange={() => toggleSelect(p.id)} /></td>
                    <td>
                      <div><strong>{p.company || p.name}</strong></div>
                      {p.address && <div style={{ fontSize: '0.85em', color: '#6B7280' }}>{p.address}</div>}
                      {p.website && <a href={p.website} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.85em' }}>{p.website}</a>}
                    </td>
                    <td>{p.business_category || '-'}</td>
                    <td style={{ color: '#F59E0B', whiteSpace: 'nowrap' }}>{renderStars(p.google_rating)}</td>
                    <td>{p.review_count || '-'}</td>
                    <td>
                      <div style={{ fontSize: '0.85em' }}>
                        {p.phone && <div>{p.phone}</div>}
                        {p.email && !p.email.includes('@unknown') ? <div>{p.email}</div> : null}
                        {!p.phone && (!p.email || p.email.includes('@unknown')) && '-'}
                      </div>
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                        <button className="btn btn-sm btn-primary" onClick={() => setShowCampaignPicker(p.id)}>
                          + Campaign
                        </button>
                        {p.qualified !== true && (
                          <button className="btn btn-sm btn-success" onClick={() => handleQualify(p.id, true)}
                            disabled={qualifyingId === p.id}>
                            {qualifyingId === p.id ? '...' : 'Qualify'}
                          </button>
                        )}
                        <button className="btn btn-sm btn-danger" onClick={() => setConfirmDismiss(p.id)}
                          disabled={dismissingId === p.id}>
                          {dismissingId === p.id ? '...' : 'Dismiss'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Campaign Picker Modal */}
      {showCampaignPicker && (
        <div className="modal-overlay" onClick={() => setShowCampaignPicker(null)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: '400px' }}>
            <div className="modal-header">
              <h3 className="modal-title">Select Campaign</h3>
              <button className="modal-close" onClick={() => setShowCampaignPicker(null)}>&times;</button>
            </div>
            <div className="modal-body">
              {campaigns.filter(c => c.status === 'draft').map(c => (
                <button key={c.id} className="btn btn-secondary" style={{ display: 'block', width: '100%', marginBottom: '8px', textAlign: 'left' }}
                  onClick={() => {
                    if (showCampaignPicker === 'bulk') handleBulkAdd(c.id);
                    else handleAddToCampaign(showCampaignPicker, c.id);
                  }}>
                  {c.name}
                </button>
              ))}
              {campaigns.filter(c => c.status === 'draft').length === 0 && (
                <p style={{ color: '#6B7280' }}>No draft campaigns. Create one first.</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Dismiss Confirmation Modal */}
      {confirmDismiss && (
        <div className="modal-overlay" onClick={() => setConfirmDismiss(null)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: '400px' }}>
            <div className="modal-header">
              <h3 className="modal-title">Dismiss Prospect</h3>
              <button className="modal-close" onClick={() => setConfirmDismiss(null)}>&times;</button>
            </div>
            <div className="modal-body">
              <p>Are you sure you want to dismiss this prospect? This will permanently remove them from your discovery list.</p>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setConfirmDismiss(null)}>Cancel</button>
              <button className="btn btn-danger" onClick={() => handleDismiss(confirmDismiss)}
                disabled={dismissingId !== null}>
                {dismissingId ? 'Dismissing...' : 'Dismiss'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Discovery;
