import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  getApolloStatus,
  searchApollo,
  importApolloToContacts,
  importApolloToCampaign,
  getCampaigns,
} from '../api/client';

function ApolloSearch() {
  const [configured, setConfigured] = useState(null);
  const [filters, setFilters] = useState({
    q_keywords: '',
    person_titles: '',
    person_locations: '',
    q_organization_domains: '',
  });
  const [results, setResults] = useState({ people: [], total: 0, page: 1, total_pages: 0 });
  const [selected, setSelected] = useState(new Set());
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [importing, setImporting] = useState(false);
  const [showCampaignPicker, setShowCampaignPicker] = useState(false);
  const [campaigns, setCampaigns] = useState([]);
  const [selectedCampaignId, setSelectedCampaignId] = useState('');

  useEffect(() => {
    getApolloStatus()
      .then((r) => setConfigured(r.data.configured))
      .catch(() => setConfigured(false));
  }, []);

  const parseCommaSeparated = (val) => {
    if (!val.trim()) return undefined;
    return val.split(',').map((s) => s.trim()).filter(Boolean);
  };

  const handleSearch = async (page = 1) => {
    setLoading(true);
    setMessage('');
    try {
      const payload = { page, per_page: 25 };
      if (filters.q_keywords.trim()) payload.q_keywords = filters.q_keywords.trim();
      if (filters.person_titles.trim()) payload.person_titles = parseCommaSeparated(filters.person_titles);
      if (filters.person_locations.trim()) payload.person_locations = parseCommaSeparated(filters.person_locations);
      if (filters.q_organization_domains.trim()) payload.q_organization_domains = parseCommaSeparated(filters.q_organization_domains);

      const res = await searchApollo(payload);
      setResults(res.data);
      setSelected(new Set());
    } catch (err) {
      const msg = err.response?.data?.error || 'Search failed';
      setMessage(msg);
    }
    setLoading(false);
  };

  const toggleSelect = (idx) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selected.size === results.people.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(results.people.map((_, i) => i)));
    }
  };

  const getSelectedPeople = () => results.people.filter((_, i) => selected.has(i));

  const handleImportToContacts = async () => {
    const people = getSelectedPeople();
    if (!people.length) return;
    setImporting(true);
    try {
      const res = await importApolloToContacts({ people, tag: 'apollo-import' });
      setMessage(`Imported ${res.data.imported} contacts (${res.data.skipped} skipped).`);
      setSelected(new Set());
    } catch (err) {
      setMessage(err.response?.data?.error || 'Import failed');
    }
    setImporting(false);
  };

  const handleOpenCampaignPicker = async () => {
    try {
      const res = await getCampaigns();
      const drafts = (res.data.campaigns || res.data || []).filter(
        (c) => c.status === 'draft' || c.status === 'paused'
      );
      setCampaigns(drafts);
      setShowCampaignPicker(true);
    } catch {
      setMessage('Failed to load campaigns');
    }
  };

  const handleImportToCampaign = async () => {
    if (!selectedCampaignId) return;
    const people = getSelectedPeople();
    if (!people.length) return;
    setImporting(true);
    try {
      const res = await importApolloToCampaign({
        campaign_id: parseInt(selectedCampaignId, 10),
        people,
      });
      setMessage(`Added ${res.data.imported} recipients to campaign (${res.data.skipped} skipped).`);
      setSelected(new Set());
      setShowCampaignPicker(false);
    } catch (err) {
      setMessage(err.response?.data?.error || 'Import failed');
    }
    setImporting(false);
  };

  if (configured === null) {
    return <div className="page-container"><p>Loading...</p></div>;
  }

  if (configured === false) {
    return (
      <div className="page-container">
        <h2>Apollo.io Search</h2>
        <div className="card">
          <p className="mb-2">Apollo API key is not configured.</p>
          <Link to="/settings" className="btn btn-primary">Go to Settings</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container">
      <h2 style={{ marginBottom: '1rem' }}>Apollo.io Search</h2>

      {message && (
        <div className="card mb-4" style={{ background: '#F0FDF4', border: '1px solid #BBF7D0' }}>
          <p style={{ margin: 0 }}>{message}</p>
        </div>
      )}

      {/* Search Filters */}
      <div className="card mb-4">
        <h3 className="card-title mb-2">Search Filters</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
          <div>
            <label className="text-sm" style={{ fontWeight: 600, display: 'block', marginBottom: '0.25rem' }}>Keywords</label>
            <input
              type="text"
              className="form-input"
              placeholder="e.g. SaaS, marketing"
              value={filters.q_keywords}
              onChange={(e) => setFilters((f) => ({ ...f, q_keywords: e.target.value }))}
              style={{ width: '100%' }}
            />
          </div>
          <div>
            <label className="text-sm" style={{ fontWeight: 600, display: 'block', marginBottom: '0.25rem' }}>Job Titles</label>
            <input
              type="text"
              className="form-input"
              placeholder="e.g. CEO, VP Sales"
              value={filters.person_titles}
              onChange={(e) => setFilters((f) => ({ ...f, person_titles: e.target.value }))}
              style={{ width: '100%' }}
            />
          </div>
          <div>
            <label className="text-sm" style={{ fontWeight: 600, display: 'block', marginBottom: '0.25rem' }}>Company Domains</label>
            <input
              type="text"
              className="form-input"
              placeholder="e.g. acme.com, stripe.com"
              value={filters.q_organization_domains}
              onChange={(e) => setFilters((f) => ({ ...f, q_organization_domains: e.target.value }))}
              style={{ width: '100%' }}
            />
          </div>
          <div>
            <label className="text-sm" style={{ fontWeight: 600, display: 'block', marginBottom: '0.25rem' }}>Locations</label>
            <input
              type="text"
              className="form-input"
              placeholder="e.g. California, New York"
              value={filters.person_locations}
              onChange={(e) => setFilters((f) => ({ ...f, person_locations: e.target.value }))}
              style={{ width: '100%' }}
            />
          </div>
        </div>
        <div style={{ marginTop: '0.75rem' }}>
          <button className="btn btn-primary" onClick={() => handleSearch(1)} disabled={loading}>
            {loading ? 'Searching...' : 'Search Apollo'}
          </button>
        </div>
      </div>

      {/* Results */}
      {results.people.length > 0 && (
        <div className="card mb-4">
          <div className="flex" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <h3 className="card-title" style={{ margin: 0 }}>
              Results ({results.total.toLocaleString()} total)
            </h3>
            {selected.size > 0 && (
              <div className="flex gap-2">
                <span className="text-sm" style={{ alignSelf: 'center' }}>{selected.size} selected</span>
                <button className="btn btn-primary btn-sm" onClick={handleImportToContacts} disabled={importing}>
                  {importing ? 'Importing...' : 'Import to Contacts'}
                </button>
                <button className="btn btn-sm" style={{ background: '#E5E7EB', color: '#374151' }} onClick={handleOpenCampaignPicker} disabled={importing}>
                  Add to Campaign
                </button>
              </div>
            )}
          </div>

          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #E5E7EB', textAlign: 'left' }}>
                <th style={{ padding: '0.5rem' }}>
                  <input type="checkbox" checked={selected.size === results.people.length && results.people.length > 0} onChange={toggleSelectAll} />
                </th>
                <th style={{ padding: '0.5rem' }}>Name</th>
                <th style={{ padding: '0.5rem' }}>Title</th>
                <th style={{ padding: '0.5rem' }}>Company</th>
                <th style={{ padding: '0.5rem' }}>Email</th>
                <th style={{ padding: '0.5rem' }}>Location</th>
              </tr>
            </thead>
            <tbody>
              {results.people.map((p, i) => (
                <tr key={i} style={{ borderBottom: '1px solid #F3F4F6', cursor: 'pointer' }} onClick={() => toggleSelect(i)}>
                  <td style={{ padding: '0.5rem' }}>
                    <input type="checkbox" checked={selected.has(i)} onChange={() => toggleSelect(i)} onClick={(e) => e.stopPropagation()} />
                  </td>
                  <td style={{ padding: '0.5rem', fontWeight: 500 }}>{p.name || '—'}</td>
                  <td style={{ padding: '0.5rem' }} className="text-sm">{p.title || '—'}</td>
                  <td style={{ padding: '0.5rem' }} className="text-sm">{p.company || '—'}</td>
                  <td style={{ padding: '0.5rem' }} className="text-sm">{p.email || <span style={{ color: '#9CA3AF' }}>No email</span>}</td>
                  <td style={{ padding: '0.5rem' }} className="text-sm">{p.address || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Pagination */}
          {results.total_pages > 1 && (
            <div className="flex gap-2" style={{ marginTop: '0.75rem', justifyContent: 'center', alignItems: 'center' }}>
              <button
                className="btn btn-sm"
                style={{ background: '#E5E7EB', color: '#374151' }}
                onClick={() => handleSearch(results.page - 1)}
                disabled={results.page <= 1 || loading}
              >
                Previous
              </button>
              <span className="text-sm">
                Page {results.page} of {results.total_pages}
              </span>
              <button
                className="btn btn-sm"
                style={{ background: '#E5E7EB', color: '#374151' }}
                onClick={() => handleSearch(results.page + 1)}
                disabled={results.page >= results.total_pages || loading}
              >
                Next
              </button>
            </div>
          )}
        </div>
      )}

      {/* Campaign Picker Modal */}
      {showCampaignPicker && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
        }} onClick={() => setShowCampaignPicker(false)}>
          <div className="card" style={{ minWidth: '400px', maxWidth: '500px' }} onClick={(e) => e.stopPropagation()}>
            <h3 className="card-title mb-2">Add to Campaign</h3>
            {campaigns.length === 0 ? (
              <p className="text-sm text-light">No draft or paused campaigns found.</p>
            ) : (
              <>
                <select
                  className="form-input"
                  style={{ width: '100%', marginBottom: '0.75rem' }}
                  value={selectedCampaignId}
                  onChange={(e) => setSelectedCampaignId(e.target.value)}
                >
                  <option value="">Select a campaign...</option>
                  {campaigns.map((c) => (
                    <option key={c.id} value={c.id}>{c.name} ({c.status})</option>
                  ))}
                </select>
                <div className="flex gap-2">
                  <button className="btn btn-primary" onClick={handleImportToCampaign} disabled={!selectedCampaignId || importing}>
                    {importing ? 'Adding...' : `Add ${selected.size} contacts`}
                  </button>
                  <button className="btn" style={{ background: '#E5E7EB', color: '#374151' }} onClick={() => setShowCampaignPicker(false)}>
                    Cancel
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default ApolloSearch;
