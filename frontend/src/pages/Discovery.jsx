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
    await qualifyProspect(id, { qualified });
    loadAll();
  };

  const handleAddToCampaign = async (prospectId, campaignId) => {
    await addProspectToCampaign(prospectId, { campaign_id: campaignId });
    setShowCampaignPicker(null);
    loadAll();
  };

  const handleBulkAdd = async (campaignId) => {
    await bulkAddProspects({ contact_ids: [...selectedProspects], campaign_id: campaignId });
    setSelectedProspects(new Set());
    setShowCampaignPicker(null);
    loadAll();
  };

  const handleDismiss = async (id) => {
    await dismissProspect(id);
    loadAll();
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
      <div className="stats-row" style={{ display: 'flex', gap: '16px', marginBottom: '20px' }}>
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
              <label>Name</label>
              <input value={newCriteria.name} onChange={e => setNewCriteria({...newCriteria, name: e.target.value})}
                placeholder="e.g. NJ Plumbers" className="input" />
            </div>
            <div>
              <label>Industries (comma-separated)</label>
              <input value={newCriteria.search_queries} onChange={e => setNewCriteria({...newCriteria, search_queries: e.target.value})}
                placeholder="plumber, plumbing company" className="input" />
            </div>
            <div>
              <label>Zip Codes (comma-separated)</label>
              <input value={newCriteria.zip_codes} onChange={e => setNewCriteria({...newCriteria, zip_codes: e.target.value})}
                placeholder="07302, 07304" className="input" />
            </div>
            <div>
              <label>Min Rating</label>
              <input type="number" min="0" max="5" step="0.5" value={newCriteria.min_rating}
                onChange={e => setNewCriteria({...newCriteria, min_rating: parseFloat(e.target.value) || 0})}
                className="input" />
            </div>
            <div>
              <label>Max Results Per Query</label>
              <input type="number" min="5" max="100" value={newCriteria.max_results_per_query}
                onChange={e => setNewCriteria({...newCriteria, max_results_per_query: parseInt(e.target.value) || 20})}
                className="input" />
            </div>
            <div>
              <label>Scan Interval (hours)</label>
              <input type="number" min="24" value={newCriteria.scan_interval_hours}
                onChange={e => setNewCriteria({...newCriteria, scan_interval_hours: parseInt(e.target.value) || 168})}
                className="input" />
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
              <div key={c.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--border-color, #e5e7eb)' }}>
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
                  <button className="btn btn-sm" onClick={() => handleScanNow(c.id)} disabled={scanning}>Scan</button>
                  <button className="btn btn-sm btn-danger" onClick={async () => {
                    await deleteDiscoveryCriteria(c.id);
                    loadAll();
                  }}>Delete</button>
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
        <h3>Discovered Prospects ({prospects.length})</h3>
        {loading ? (
          <p>Loading...</p>
        ) : prospects.length === 0 ? (
          <p style={{ color: '#6B7280' }}>No prospects discovered yet. Create search criteria and run a scan.</p>
        ) : (
          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th><input type="checkbox" onChange={(e) => {
                    if (e.target.checked) setSelectedProspects(new Set(prospects.map(p => p.id)));
                    else setSelectedProspects(new Set());
                  }} /></th>
                  <th>Business</th>
                  <th>Category</th>
                  <th>Rating</th>
                  <th>Reviews</th>
                  <th>Phone</th>
                  <th>Email</th>
                  <th>Actions</th>
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
                    <td style={{ color: '#F59E0B' }}>{renderStars(p.google_rating)}</td>
                    <td>{p.review_count || '-'}</td>
                    <td>{p.phone || '-'}</td>
                    <td style={{ fontSize: '0.85em' }}>{p.email && !p.email.includes('@unknown') ? p.email : '-'}</td>
                    <td>
                      <div style={{ display: 'flex', gap: '4px' }}>
                        <button className="btn btn-sm btn-primary" onClick={() => setShowCampaignPicker(p.id)}>
                          + Campaign
                        </button>
                        {p.qualified === null && (
                          <>
                            <button className="btn btn-sm" onClick={() => handleQualify(p.id, true)}
                              style={{ color: '#10B981' }}>Qualify</button>
                            <button className="btn btn-sm" onClick={() => handleDismiss(p.id)}
                              style={{ color: '#EF4444' }}>Dismiss</button>
                          </>
                        )}
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
            <h3>Select Campaign</h3>
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
            <button className="btn btn-secondary" style={{ marginTop: '12px' }} onClick={() => setShowCampaignPicker(null)}>Cancel</button>
          </div>
        </div>
      )}
    </div>
  );
}

export default Discovery;
