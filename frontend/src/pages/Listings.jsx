import { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  getMonitoredSites,
  createMonitoredSite,
  uploadBrokerSites,
  deleteMonitoredSite,
  checkSiteNow,
  checkAllSitesNow,
  getListings,
  getListingStats,
  getListingFilterOptions,
  markListingSeen,
  markAllListingsSeen,
  updateListingNotes,
  fetchSiteInfo,
  getContacts,
  getDealCriteria,
  updateDealCriteria,
  getStandardCategories,
  quickAddListing,
  parseEmailPreview,
  ingestEmailListing,
  scanEmailAlerts,
  createDealFromListing,
} from '../api/client';
import { formatPrice } from '../utils/format';

// Price presets for quick selection
const PRICE_PRESETS = [
  { label: 'Any', min: '', max: '' },
  { label: 'Under $100K', min: '', max: '100000' },
  { label: '$100K – $250K', min: '100000', max: '250000' },
  { label: '$250K – $500K', min: '250000', max: '500000' },
  { label: '$500K – $1M', min: '500000', max: '1000000' },
  { label: '$1M – $5M', min: '1000000', max: '5000000' },
  { label: 'Over $5M', min: '5000000', max: '' },
];

function Listings() {
  const [sites, setSites] = useState([]);
  const [listings, setListings] = useState({ groups: [], total: 0, new_count: 0 });
  const [stats, setStats] = useState({});
  const [contacts, setContacts] = useState([]);
  const [filterOptions, setFilterOptions] = useState({ locations: [], categories: [], price_min: null, price_max: null });
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [checkingSiteId, setCheckingSiteId] = useState(null);

  // Add site form
  const [showAddForm, setShowAddForm] = useState(false);
  const [newSite, setNewSite] = useState({ name: '', url: '', contact_id: '', check_interval_hours: 24 });
  const [fetchingName, setFetchingName] = useState(false);

  // CSV upload
  const [showCsvUpload, setShowCsvUpload] = useState(false);
  const [uploadFile, setUploadFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);

  // Filters
  const [filterSiteId, setFilterSiteId] = useState(null);
  const [showNewOnly, setShowNewOnly] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState({
    price_min: '',
    price_max: '',
    location: '',
    category: '',
    q: '',
  });
  const [appliedFilters, setAppliedFilters] = useState({});

  // Notes editing
  const [editingNotes, setEditingNotes] = useState(null);

  // Deal criteria (intake filters)
  const [dealCriteria, setDealCriteria] = useState(null);
  const [showDealCriteria, setShowDealCriteria] = useState(false);
  const [savingCriteria, setSavingCriteria] = useState(false);

  // Quick-add form
  const [showQuickAdd, setShowQuickAdd] = useState(false);
  const [quickAdd, setQuickAdd] = useState({
    title: '', price: '', url: '', location: '', category: '', description: '',
  });
  const [savingQuickAdd, setSavingQuickAdd] = useState(false);
  const [standardCategories, setStandardCategories] = useState([]);

  // Email ingestion
  const [showEmailIngest, setShowEmailIngest] = useState(false);
  const [emailIngest, setEmailIngest] = useState({ subject: '', body: '', broker_name: '' });
  const [emailParsed, setEmailParsed] = useState(null);
  const [parsingEmail, setParsingEmail] = useState(false);
  const [savingEmail, setSavingEmail] = useState(false);
  const [scanningAlerts, setScanningAlerts] = useState(false);
  const [scanResult, setScanResult] = useState(null);
  const [alertDaysBack, setAlertDaysBack] = useState(7);
  const [alertCustomQuery, setAlertCustomQuery] = useState('');

  // Debounce keyword search
  const [keywordTimer, setKeywordTimer] = useState(null);
  const navigate = useNavigate();

  const handleTrackDeal = async (listing) => {
    try {
      await createDealFromListing(listing.id);
      navigate('/deals');
    } catch (err) {
      console.error('Failed to create deal:', err);
    }
  };

  useEffect(() => {
    loadData();
    loadFilterOptions();
    loadDealCriteria();
    loadStandardCategories();
    const handleWsChange = () => { loadData(); loadFilterOptions(); loadDealCriteria(); };
    window.addEventListener('workspace-changed', handleWsChange);
    return () => window.removeEventListener('workspace-changed', handleWsChange);
  }, [filterSiteId, showNewOnly, appliedFilters]);

  const loadData = async () => {
    setLoading(true);
    try {
      const params = { ...appliedFilters };
      if (filterSiteId) params.site_id = filterSiteId;
      if (showNewOnly) params.new_only = 'true';

      const [sitesRes, listingsRes, statsRes, contactsRes] = await Promise.all([
        getMonitoredSites(),
        getListings(params),
        getListingStats(),
        getContacts({ per_page: 200 }),
      ]);

      setSites(sitesRes.data || []);
      setListings(listingsRes.data || { groups: [], total: 0, new_count: 0 });
      setStats(statsRes.data || {});
      setContacts(contactsRes.data?.contacts || contactsRes.data || []);
    } catch (err) {
      console.error('Failed to load listings data:', err);
    }
    setLoading(false);
  };

  const loadFilterOptions = async () => {
    try {
      const res = await getListingFilterOptions();
      setFilterOptions(res.data || { locations: [], categories: [], price_min: null, price_max: null });
    } catch {
      // Non-critical
    }
  };

  const loadDealCriteria = async () => {
    try {
      const res = await getDealCriteria();
      setDealCriteria(res.data || null);
    } catch {
      // Non-critical
    }
  };

  const handleSaveDealCriteria = async () => {
    if (!dealCriteria) return;
    setSavingCriteria(true);
    try {
      const res = await updateDealCriteria(dealCriteria);
      setDealCriteria(res.data);
      alert(dealCriteria.is_active
        ? 'Deal criteria saved! Only matching listings will be imported on future scrapes.'
        : 'Deal criteria saved (disabled). All listings will be imported.');
    } catch (err) {
      console.error('Failed to save deal criteria:', err);
      alert('Failed to save deal criteria');
    }
    setSavingCriteria(false);
  };

  const applyFilters = useCallback(() => {
    const newApplied = {};
    if (filters.price_min) newApplied.price_min = filters.price_min;
    if (filters.price_max) newApplied.price_max = filters.price_max;
    if (filters.location) newApplied.location = filters.location;
    if (filters.category) newApplied.category = filters.category;
    if (filters.q) newApplied.q = filters.q;
    setAppliedFilters(newApplied);
  }, [filters]);

  const clearFilters = () => {
    setFilters({ price_min: '', price_max: '', location: '', category: '', q: '' });
    setAppliedFilters({});
  };

  const activeFilterCount = Object.keys(appliedFilters).length;

  const handleKeywordChange = (value) => {
    setFilters(prev => ({ ...prev, q: value }));
    // Debounce: auto-apply after 500ms
    if (keywordTimer) clearTimeout(keywordTimer);
    const timer = setTimeout(() => {
      setAppliedFilters(prev => {
        const next = { ...prev };
        if (value) next.q = value;
        else delete next.q;
        return next;
      });
    }, 500);
    setKeywordTimer(timer);
  };

  const handlePricePreset = (preset) => {
    setFilters(prev => ({ ...prev, price_min: preset.min, price_max: preset.max }));
    // Auto-apply
    setAppliedFilters(prev => {
      const next = { ...prev };
      if (preset.min) next.price_min = preset.min; else delete next.price_min;
      if (preset.max) next.price_max = preset.max; else delete next.price_max;
      return next;
    });
  };

  const handleUrlChange = async (url) => {
    setNewSite((prev) => ({ ...prev, url }));
    const trimmed = url.trim();
    if (trimmed.startsWith('http') && !newSite.name) {
      setFetchingName(true);
      try {
        const res = await fetchSiteInfo(trimmed);
        if (res.data?.name) {
          setNewSite((prev) => prev.name ? prev : { ...prev, name: res.data.name });
        }
      } catch {
        // Ignore fetch errors
      }
      setFetchingName(false);
    }
  };

  const handleAddSite = async () => {
    if (!newSite.url.trim()) return;
    try {
      await createMonitoredSite({
        ...newSite,
        contact_id: newSite.contact_id || null,
      });
      setNewSite({ name: '', url: '', contact_id: '', check_interval_hours: 24 });
      setShowAddForm(false);
      loadData();
    } catch (err) {
      console.error('Failed to add site:', err);
      alert('Failed to add site');
    }
  };

  const handleCsvUpload = async () => {
    if (!uploadFile) return;
    setUploading(true);
    setUploadResult(null);
    try {
      const res = await uploadBrokerSites(uploadFile);
      setUploadResult(res.data);
      if (res.data.created > 0) {
        loadData();
      }
    } catch (err) {
      const errData = err.response?.data || {};
      setUploadResult({ error: errData.error || 'Upload failed', headers: errData.headers });
    }
    setUploading(false);
  };

  const handleDeleteSite = async (siteId) => {
    if (!confirm('Remove this site and all its listings?')) return;
    try {
      await deleteMonitoredSite(siteId);
      loadData();
    } catch (err) {
      console.error('Failed to delete site:', err);
    }
  };

  const handleCheckSite = async (siteId) => {
    setCheckingSiteId(siteId);
    try {
      const res = await checkSiteNow(siteId);
      const data = res.data || {};
      if (data.error) {
        alert(`Scrape error: ${data.error}`);
      } else if (data.total_scraped === 0 && data.hint) {
        alert(data.hint);
      } else {
        let msg = `Found ${data.new || 0} new listing(s), ${data.total_scraped || 0} total on page`;
        if (data.filtered_out) msg += ` (${data.filtered_out} filtered out by deal criteria)`;
        alert(msg);
      }
      loadData();
      loadFilterOptions();
    } catch (err) {
      console.error('Check failed:', err);
      alert('Failed to check site');
    }
    setCheckingSiteId(null);
  };

  const handleCheckAll = async () => {
    setChecking(true);
    try {
      const res = await checkAllSitesNow();
      const results = res.data || [];
      const totalNew = results.reduce((sum, r) => sum + (r.new || 0), 0);
      const errors = results.filter((r) => r.error);
      let msg = `Checked ${results.length} site(s). ${totalNew} new listing(s) found.`;
      if (errors.length > 0) msg += ` ${errors.length} site(s) had errors.`;
      alert(msg);
      loadData();
      loadFilterOptions();
    } catch (err) {
      console.error('Check all failed:', err);
      alert('Failed to check sites');
    }
    setChecking(false);
  };

  const handleMarkSeen = async (listingId) => {
    try {
      await markListingSeen(listingId);
      loadData();
    } catch (err) {
      console.error('Mark seen failed:', err);
    }
  };

  const handleMarkAllSeen = async (siteId) => {
    try {
      await markAllListingsSeen(siteId);
      loadData();
    } catch (err) {
      console.error('Mark all seen failed:', err);
    }
  };

  const handleSaveNotes = async (listingId, notes) => {
    try {
      await updateListingNotes(listingId, notes);
      setEditingNotes(null);
      loadData();
    } catch (err) {
      console.error('Save notes failed:', err);
    }
  };

  const loadStandardCategories = async () => {
    try {
      const res = await getStandardCategories();
      setStandardCategories(res.data || []);
    } catch {
      // Non-critical
    }
  };

  const handleQuickAdd = async () => {
    if (!quickAdd.title.trim()) return;
    setSavingQuickAdd(true);
    try {
      await quickAddListing(quickAdd);
      setQuickAdd({ title: '', price: '', url: '', location: '', category: '', description: '' });
      setShowQuickAdd(false);
      loadData();
      loadFilterOptions();
    } catch (err) {
      const msg = err.response?.data?.error || 'Failed to add listing';
      alert(msg);
    }
    setSavingQuickAdd(false);
  };

  const handleParseEmail = async () => {
    if (!emailIngest.body.trim()) return;
    setParsingEmail(true);
    try {
      const res = await parseEmailPreview(emailIngest);
      setEmailParsed(res.data);
    } catch (err) {
      console.error('Parse failed:', err);
      alert('Failed to parse email');
    }
    setParsingEmail(false);
  };

  const handleScanAlerts = async () => {
    setScanningAlerts(true);
    setScanResult(null);
    try {
      const res = await scanEmailAlerts({
        days_back: alertDaysBack,
        custom_query: alertCustomQuery,
      });
      setScanResult(res.data);
      if (res.data?.listings_ingested > 0) {
        loadData();
        loadFilterOptions();
      }
    } catch (err) {
      const msg = err.response?.data?.error || 'Failed to scan emails';
      setScanResult({ error: msg });
    }
    setScanningAlerts(false);
  };

  const handleIngestEmail = async () => {
    setSavingEmail(true);
    try {
      const res = await ingestEmailListing(emailIngest);
      setEmailIngest({ subject: '', body: '', broker_name: '' });
      setEmailParsed(null);
      setShowEmailIngest(false);
      loadData();
      loadFilterOptions();
    } catch (err) {
      const msg = err.response?.data?.error || 'Failed to ingest email';
      alert(msg);
    }
    setSavingEmail(false);
  };

  if (loading && !listings.groups.length) {
    return (
      <div>
        <h1 className="mb-4">Listing Monitor</h1>
        <div className="card" style={{ textAlign: 'center', padding: '40px' }}>Loading...</div>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h1 style={{ margin: 0 }}>Listing Monitor</h1>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            className={`btn ${showDealCriteria ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setShowDealCriteria(!showDealCriteria)}
            style={{ position: 'relative' }}
          >
            Deal Criteria
            {dealCriteria?.is_active && (
              <span style={{
                position: 'absolute', top: '-6px', right: '-6px',
                backgroundColor: '#059669', color: '#fff', borderRadius: '50%',
                width: '14px', height: '14px', fontSize: '10px',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>✓</span>
            )}
          </button>
          <button
            className={`btn ${showFilters ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setShowFilters(!showFilters)}
            style={{ position: 'relative' }}
          >
            Filters
            {activeFilterCount > 0 && (
              <span style={{
                position: 'absolute',
                top: '-6px',
                right: '-6px',
                backgroundColor: '#EF4444',
                color: '#fff',
                borderRadius: '10px',
                padding: '0 6px',
                fontSize: '11px',
                fontWeight: 700,
                minWidth: '18px',
                textAlign: 'center',
              }}>
                {activeFilterCount}
              </span>
            )}
          </button>
          <button
            className="btn btn-secondary"
            onClick={handleCheckAll}
            disabled={checking}
          >
            {checking ? 'Checking...' : 'Check All Sites'}
          </button>
          <button
            className={`btn ${showEmailIngest ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => { setShowEmailIngest(!showEmailIngest); setShowQuickAdd(false); }}
          >
            Email Ingest
          </button>
          <button
            className={`btn ${showQuickAdd ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => { setShowQuickAdd(!showQuickAdd); setShowEmailIngest(false); }}
          >
            + Quick Add
          </button>
          <button
            className={`btn ${showCsvUpload ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => { setShowCsvUpload(!showCsvUpload); setShowAddForm(false); setUploadFile(null); setUploadResult(null); }}
          >
            Upload CSV
          </button>
          <button
            className="btn btn-primary"
            onClick={() => { setShowAddForm(!showAddForm); setShowCsvUpload(false); }}
          >
            + Add Site
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', marginBottom: '20px' }}>
        <div className="card" style={{ textAlign: 'center', padding: '16px' }}>
          <div style={{ fontSize: '28px', fontWeight: 700, color: '#3B82F6' }}>{stats.active_sites || 0}</div>
          <div className="text-sm text-light">Sites Monitored</div>
        </div>
        <div className="card" style={{ textAlign: 'center', padding: '16px' }}>
          <div style={{ fontSize: '28px', fontWeight: 700, color: '#E8603C' }}>{stats.total_listings || 0}</div>
          <div className="text-sm text-light">Total Listings</div>
        </div>
        <div className="card" style={{ textAlign: 'center', padding: '16px' }}>
          <div style={{ fontSize: '28px', fontWeight: 700, color: '#F59E0B' }}>{stats.new_listings || 0}</div>
          <div className="text-sm text-light">New Listings</div>
        </div>
        <div className="card" style={{ textAlign: 'center', padding: '16px', cursor: 'pointer', border: showNewOnly ? '2px solid #F59E0B' : undefined }}
          onClick={() => setShowNewOnly(!showNewOnly)}
        >
          <div style={{ fontSize: '14px', fontWeight: 600, color: showNewOnly ? '#F59E0B' : '#6B7280' }}>
            {showNewOnly ? 'Showing New Only' : 'Show New Only'}
          </div>
        </div>
      </div>

      {/* ─── Deal Criteria (Intake Filters) ─── */}
      {showDealCriteria && dealCriteria && (
        <div className="card" style={{ marginBottom: '20px', padding: '20px', borderLeft: `4px solid ${dealCriteria.is_active ? '#059669' : '#D1D5DB'}` }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <div>
              <h3 style={{ margin: 0, fontSize: '16px' }}>Deal Criteria</h3>
              <p className="text-sm text-light" style={{ margin: '4px 0 0' }}>
                {dealCriteria.is_active
                  ? 'Active — only listings matching these criteria will be imported when scraping.'
                  : 'Disabled — all listings will be imported regardless of criteria.'}
              </p>
            </div>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={dealCriteria.is_active}
                onChange={(e) => setDealCriteria({ ...dealCriteria, is_active: e.target.checked })}
              />
              <span style={{ fontSize: '14px', fontWeight: 600, color: dealCriteria.is_active ? '#059669' : '#6B7280' }}>
                {dealCriteria.is_active ? 'Enabled' : 'Disabled'}
              </span>
            </label>
          </div>

          {/* Financial Range Inputs */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', marginBottom: '16px' }}>
            {[
              { label: 'Asking Price', minKey: 'price_min', maxKey: 'price_max' },
              { label: 'Revenue', minKey: 'revenue_min', maxKey: 'revenue_max' },
              { label: 'Cash Flow', minKey: 'cash_flow_min', maxKey: 'cash_flow_max' },
              { label: 'SDE', minKey: 'sde_min', maxKey: 'sde_max' },
              { label: 'EBITDA', minKey: 'ebitda_min', maxKey: 'ebitda_max' },
              { label: 'Net Profit', minKey: 'net_profit_min', maxKey: 'net_profit_max' },
            ].map(({ label, minKey, maxKey }) => (
              <div key={label}>
                <label className="text-sm" style={{ fontWeight: 600, display: 'block', marginBottom: '4px' }}>{label}</label>
                <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                  <input
                    className="input"
                    type="number"
                    placeholder="Min"
                    value={dealCriteria[minKey] ?? ''}
                    onChange={(e) => setDealCriteria({ ...dealCriteria, [minKey]: e.target.value })}
                    style={{ width: '100%', fontSize: '13px' }}
                  />
                  <span style={{ color: '#9CA3AF', fontSize: '12px' }}>–</span>
                  <input
                    className="input"
                    type="number"
                    placeholder="Max"
                    value={dealCriteria[maxKey] ?? ''}
                    onChange={(e) => setDealCriteria({ ...dealCriteria, [maxKey]: e.target.value })}
                    style={{ width: '100%', fontSize: '13px' }}
                  />
                </div>
              </div>
            ))}
          </div>

          {/* Text filters */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
            <div>
              <label className="text-sm" style={{ fontWeight: 600, display: 'block', marginBottom: '4px' }}>
                Locations (comma-separated)
              </label>
              <input
                className="input"
                placeholder="e.g. New Jersey, Bergen County"
                value={dealCriteria.locations || ''}
                onChange={(e) => setDealCriteria({ ...dealCriteria, locations: e.target.value })}
              />
            </div>
            <div>
              <label className="text-sm" style={{ fontWeight: 600, display: 'block', marginBottom: '4px' }}>
                Categories (comma-separated)
              </label>
              <input
                className="input"
                placeholder="e.g. Restaurant, Auto Body, Retail"
                value={dealCriteria.categories || ''}
                onChange={(e) => setDealCriteria({ ...dealCriteria, categories: e.target.value })}
              />
            </div>
            <div>
              <label className="text-sm" style={{ fontWeight: 600, display: 'block', marginBottom: '4px' }}>
                Must contain keywords (comma-separated)
              </label>
              <input
                className="input"
                placeholder="e.g. franchise, SBA, owner-operator"
                value={dealCriteria.include_keywords || ''}
                onChange={(e) => setDealCriteria({ ...dealCriteria, include_keywords: e.target.value })}
              />
            </div>
            <div>
              <label className="text-sm" style={{ fontWeight: 600, display: 'block', marginBottom: '4px' }}>
                Exclude keywords (comma-separated)
              </label>
              <input
                className="input"
                placeholder="e.g. gas station, laundromat"
                value={dealCriteria.exclude_keywords || ''}
                onChange={(e) => setDealCriteria({ ...dealCriteria, exclude_keywords: e.target.value })}
              />
            </div>
          </div>

          <div style={{ display: 'flex', gap: '8px' }}>
            <button className="btn btn-primary" onClick={handleSaveDealCriteria} disabled={savingCriteria}>
              {savingCriteria ? 'Saving...' : 'Save Deal Criteria'}
            </button>
            <button className="btn btn-secondary" onClick={() => setShowDealCriteria(false)}>
              Close
            </button>
          </div>
        </div>
      )}

      {/* ─── Filter Panel ─── */}
      {showFilters && (
        <div className="card" style={{ marginBottom: '20px', padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ margin: 0, fontSize: '16px' }}>Filter Listings</h3>
            {activeFilterCount > 0 && (
              <button className="btn btn-secondary btn-sm" onClick={clearFilters}>
                Clear All Filters
              </button>
            )}
          </div>

          {/* Keyword Search */}
          <div style={{ marginBottom: '16px' }}>
            <label className="text-sm" style={{ fontWeight: 600, display: 'block', marginBottom: '6px' }}>
              Search Keywords
            </label>
            <input
              className="input"
              placeholder="Search title & description (e.g. franchise, SBA, owner-operator)..."
              value={filters.q}
              onChange={(e) => handleKeywordChange(e.target.value)}
              style={{ maxWidth: '600px' }}
            />
          </div>

          {/* Price Range */}
          <div style={{ marginBottom: '16px' }}>
            <label className="text-sm" style={{ fontWeight: 600, display: 'block', marginBottom: '6px' }}>
              Price Range
              {filterOptions.price_min != null && filterOptions.price_max != null && (
                <span style={{ fontWeight: 400, color: '#9CA3AF', marginLeft: '8px' }}>
                  (your listings: {formatPrice(filterOptions.price_min)} – {formatPrice(filterOptions.price_max)})
                </span>
              )}
            </label>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '8px' }}>
              {PRICE_PRESETS.map((preset) => {
                const isActive = filters.price_min === preset.min && filters.price_max === preset.max;
                return (
                  <button
                    key={preset.label}
                    className={`btn btn-sm ${isActive ? 'btn-primary' : 'btn-secondary'}`}
                    onClick={() => handlePricePreset(preset)}
                    style={{ borderRadius: '20px', fontSize: '12px' }}
                  >
                    {preset.label}
                  </button>
                );
              })}
            </div>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <input
                className="input"
                type="number"
                placeholder="Min ($)"
                value={filters.price_min}
                onChange={(e) => setFilters(prev => ({ ...prev, price_min: e.target.value }))}
                style={{ width: '140px' }}
              />
              <span style={{ color: '#9CA3AF' }}>—</span>
              <input
                className="input"
                type="number"
                placeholder="Max ($)"
                value={filters.price_max}
                onChange={(e) => setFilters(prev => ({ ...prev, price_max: e.target.value }))}
                style={{ width: '140px' }}
              />
            </div>
          </div>

          {/* Location & Category row */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
            <div>
              <label className="text-sm" style={{ fontWeight: 600, display: 'block', marginBottom: '6px' }}>
                Location
              </label>
              {filterOptions.locations.length > 0 ? (
                <select
                  className="input"
                  value={filters.location}
                  onChange={(e) => {
                    const val = e.target.value;
                    setFilters(prev => ({ ...prev, location: val }));
                    setAppliedFilters(prev => {
                      const next = { ...prev };
                      if (val) next.location = val; else delete next.location;
                      return next;
                    });
                  }}
                >
                  <option value="">All Locations</option>
                  {filterOptions.locations.map((loc) => (
                    <option key={loc} value={loc}>{loc}</option>
                  ))}
                </select>
              ) : (
                <input
                  className="input"
                  placeholder="e.g. New Jersey, Bergen County..."
                  value={filters.location}
                  onChange={(e) => setFilters(prev => ({ ...prev, location: e.target.value }))}
                />
              )}
            </div>

            <div>
              <label className="text-sm" style={{ fontWeight: 600, display: 'block', marginBottom: '6px' }}>
                Category / Industry
              </label>
              {filterOptions.categories.length > 0 ? (
                <select
                  className="input"
                  value={filters.category}
                  onChange={(e) => {
                    const val = e.target.value;
                    setFilters(prev => ({ ...prev, category: val }));
                    setAppliedFilters(prev => {
                      const next = { ...prev };
                      if (val) next.category = val; else delete next.category;
                      return next;
                    });
                  }}
                >
                  <option value="">All Categories</option>
                  {filterOptions.categories.map((cat) => (
                    <option key={cat} value={cat}>{cat}</option>
                  ))}
                </select>
              ) : (
                <input
                  className="input"
                  placeholder="e.g. Restaurant, Auto Body, Retail..."
                  value={filters.category}
                  onChange={(e) => setFilters(prev => ({ ...prev, category: e.target.value }))}
                />
              )}
            </div>
          </div>

          {/* Apply button (for price manual entry) */}
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <button className="btn btn-primary btn-sm" onClick={applyFilters}>
              Apply Filters
            </button>
            {activeFilterCount > 0 && (
              <span className="text-sm text-light">
                {listings.total} listing{listings.total !== 1 ? 's' : ''} match{listings.total === 1 ? 'es' : ''}
              </span>
            )}
          </div>
        </div>
      )}

      {/* ─── Quick Add Form ─── */}
      {showQuickAdd && (
        <div className="card" style={{ marginBottom: '20px', padding: '20px', borderLeft: '4px solid #E8603C' }}>
          <h3 style={{ margin: '0 0 12px 0', fontSize: '16px' }}>Quick Add Listing</h3>
          <p className="text-sm text-light" style={{ margin: '0 0 16px 0' }}>
            Manually add a listing you spotted outside the scrapers — paste in the details below.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: '12px', marginBottom: '12px' }}>
            <div>
              <label className="text-sm" style={{ fontWeight: 600, display: 'block', marginBottom: '4px' }}>
                Title <span style={{ color: '#EF4444' }}>*</span>
              </label>
              <input
                className="input"
                placeholder="e.g. Pizza Restaurant in Bergen County"
                value={quickAdd.title}
                onChange={(e) => setQuickAdd({ ...quickAdd, title: e.target.value })}
              />
            </div>
            <div>
              <label className="text-sm" style={{ fontWeight: 600, display: 'block', marginBottom: '4px' }}>Asking Price</label>
              <input
                className="input"
                placeholder="e.g. $450,000"
                value={quickAdd.price}
                onChange={(e) => setQuickAdd({ ...quickAdd, price: e.target.value })}
              />
            </div>
            <div>
              <label className="text-sm" style={{ fontWeight: 600, display: 'block', marginBottom: '4px' }}>Location</label>
              <input
                className="input"
                placeholder="e.g. Hackensack, NJ"
                value={quickAdd.location}
                onChange={(e) => setQuickAdd({ ...quickAdd, location: e.target.value })}
              />
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '12px', marginBottom: '12px' }}>
            <div>
              <label className="text-sm" style={{ fontWeight: 600, display: 'block', marginBottom: '4px' }}>Listing URL</label>
              <input
                className="input"
                placeholder="https://..."
                value={quickAdd.url}
                onChange={(e) => setQuickAdd({ ...quickAdd, url: e.target.value })}
              />
            </div>
            <div>
              <label className="text-sm" style={{ fontWeight: 600, display: 'block', marginBottom: '4px' }}>Category</label>
              <select
                className="input"
                value={quickAdd.category}
                onChange={(e) => setQuickAdd({ ...quickAdd, category: e.target.value })}
              >
                <option value="">— Select —</option>
                {standardCategories.map((cat) => (
                  <option key={cat} value={cat}>{cat}</option>
                ))}
              </select>
            </div>
          </div>
          <div style={{ marginBottom: '12px' }}>
            <label className="text-sm" style={{ fontWeight: 600, display: 'block', marginBottom: '4px' }}>
              Description / Notes
            </label>
            <textarea
              className="input"
              rows={3}
              placeholder="Paste listing details, financials, etc. (Revenue: $X, SDE: $X will be auto-parsed)"
              value={quickAdd.description}
              onChange={(e) => setQuickAdd({ ...quickAdd, description: e.target.value })}
              style={{ resize: 'vertical' }}
            />
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button className="btn btn-primary" onClick={handleQuickAdd} disabled={!quickAdd.title.trim() || savingQuickAdd}>
              {savingQuickAdd ? 'Adding...' : 'Add Listing'}
            </button>
            <button className="btn btn-secondary" onClick={() => setShowQuickAdd(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* ─── Email Ingestion ─── */}
      {showEmailIngest && (
        <div className="card" style={{ marginBottom: '20px', padding: '20px', borderLeft: '4px solid #3B82F6' }}>
          <h3 style={{ margin: '0 0 12px 0', fontSize: '16px' }}>Email Listing Ingestion</h3>

          {/* ── Auto-Scan Gmail Section ── */}
          <div style={{
            backgroundColor: '#F0F9FF',
            borderRadius: '10px',
            padding: '16px',
            marginBottom: '20px',
            border: '1px solid #BAE6FD',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
              <div>
                <h4 style={{ margin: '0 0 4px 0', fontSize: '14px', color: '#0369A1' }}>
                  Auto-Scan Gmail for BizBuySell Alerts
                </h4>
                <p className="text-sm text-light" style={{ margin: 0 }}>
                  Automatically find and import listings from BizBuySell saved search emails in your inbox.
                  Set up saved searches on BizBuySell, and we'll pull the listings from the alert emails — bypassing their site block.
                </p>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '12px', alignItems: 'end', marginBottom: '12px' }}>
              <div>
                <label className="text-sm" style={{ fontWeight: 600, display: 'block', marginBottom: '4px' }}>
                  Days back
                </label>
                <select
                  className="input"
                  value={alertDaysBack}
                  onChange={(e) => setAlertDaysBack(Number(e.target.value))}
                  style={{ width: '120px' }}
                >
                  <option value={1}>1 day</option>
                  <option value={3}>3 days</option>
                  <option value={7}>7 days</option>
                  <option value={14}>14 days</option>
                  <option value={30}>30 days</option>
                </select>
              </div>
              <div style={{ flex: 1 }}>
                <label className="text-sm" style={{ fontWeight: 600, display: 'block', marginBottom: '4px' }}>
                  Custom Gmail query (optional)
                </label>
                <input
                  className="input"
                  placeholder='e.g. from:broker@example.com subject:"new listing"'
                  value={alertCustomQuery}
                  onChange={(e) => setAlertCustomQuery(e.target.value)}
                />
              </div>
              <button
                className="btn btn-primary"
                onClick={handleScanAlerts}
                disabled={scanningAlerts}
                style={{ whiteSpace: 'nowrap' }}
              >
                {scanningAlerts ? 'Scanning...' : 'Scan Gmail'}
              </button>
            </div>

            {/* Scan results */}
            {scanResult && (
              <div style={{
                backgroundColor: scanResult.error ? '#FEF2F2' : '#F0FDF4',
                borderRadius: '8px',
                padding: '12px',
                fontSize: '13px',
                border: `1px solid ${scanResult.error ? '#FECACA' : '#BBF7D0'}`,
              }}>
                {scanResult.error ? (
                  <span style={{ color: '#DC2626' }}>{scanResult.error}</span>
                ) : (
                  <div>
                    <span style={{ fontWeight: 600, color: '#166534' }}>
                      Scan complete!
                    </span>{' '}
                    Found {scanResult.emails_found} email{scanResult.emails_found !== 1 ? 's' : ''}.{' '}
                    <strong>{scanResult.listings_ingested}</strong> new listing{scanResult.listings_ingested !== 1 ? 's' : ''} imported.{' '}
                    {scanResult.duplicates_skipped > 0 && (
                      <span>{scanResult.duplicates_skipped} duplicate{scanResult.duplicates_skipped !== 1 ? 's' : ''} skipped. </span>
                    )}
                    {scanResult.errors > 0 && (
                      <span style={{ color: '#B45309' }}>{scanResult.errors} error{scanResult.errors !== 1 ? 's' : ''}. </span>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* ── Manual Paste Section ── */}
          <h4 style={{ margin: '0 0 8px 0', fontSize: '14px', color: '#374151' }}>Or paste an email manually</h4>
          <p className="text-sm text-light" style={{ margin: '0 0 16px 0' }}>
            Paste a broker email below and we'll extract the listing details automatically.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '12px', marginBottom: '12px' }}>
            <div>
              <label className="text-sm" style={{ fontWeight: 600, display: 'block', marginBottom: '4px' }}>
                Email Subject
              </label>
              <input
                className="input"
                placeholder="e.g. New Listing: Pizza Restaurant - $450K"
                value={emailIngest.subject}
                onChange={(e) => setEmailIngest({ ...emailIngest, subject: e.target.value })}
              />
            </div>
            <div>
              <label className="text-sm" style={{ fontWeight: 600, display: 'block', marginBottom: '4px' }}>
                Broker Name (optional)
              </label>
              <input
                className="input"
                placeholder="e.g. NJ Broker Plus"
                value={emailIngest.broker_name}
                onChange={(e) => setEmailIngest({ ...emailIngest, broker_name: e.target.value })}
              />
            </div>
          </div>
          <div style={{ marginBottom: '12px' }}>
            <label className="text-sm" style={{ fontWeight: 600, display: 'block', marginBottom: '4px' }}>
              Email Body <span style={{ color: '#EF4444' }}>*</span>
            </label>
            <textarea
              className="input"
              rows={6}
              placeholder="Paste the full email body here..."
              value={emailIngest.body}
              onChange={(e) => setEmailIngest({ ...emailIngest, body: e.target.value })}
              style={{ resize: 'vertical', fontFamily: 'monospace', fontSize: '13px' }}
            />
          </div>

          <div style={{ display: 'flex', gap: '8px', marginBottom: emailParsed ? '16px' : 0 }}>
            <button className="btn btn-secondary" onClick={handleParseEmail} disabled={!emailIngest.body.trim() || parsingEmail}>
              {parsingEmail ? 'Parsing...' : 'Preview Extracted Data'}
            </button>
            <button className="btn btn-primary" onClick={handleIngestEmail} disabled={!emailIngest.body.trim() || savingEmail}>
              {savingEmail ? 'Saving...' : 'Ingest & Save Listing'}
            </button>
            <button className="btn btn-secondary" onClick={() => { setShowEmailIngest(false); setEmailParsed(null); }}>
              Cancel
            </button>
          </div>

          {/* Parsed preview */}
          {emailParsed && (
            <div style={{
              backgroundColor: '#F0F9FF',
              borderRadius: '8px',
              padding: '16px',
              border: '1px solid #BAE6FD',
            }}>
              <h4 style={{ margin: '0 0 10px 0', fontSize: '14px', color: '#0369A1' }}>
                Extracted Fields Preview
              </h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '13px' }}>
                {[
                  ['Title', emailParsed.title],
                  ['Price', emailParsed.price],
                  ['Location', emailParsed.location],
                  ['Category', emailParsed.category
                    ? `${emailParsed.category}${emailParsed.normalized_category ? ` → ${emailParsed.normalized_category}` : ''}`
                    : null],
                  ['URL', emailParsed.url],
                ].map(([label, value]) => (
                  <div key={label}>
                    <span style={{ fontWeight: 600, color: '#374151' }}>{label}:</span>{' '}
                    <span style={{ color: value ? '#111827' : '#9CA3AF' }}>
                      {value || 'Not found'}
                    </span>
                  </div>
                ))}
              </div>
              {emailParsed.description && (
                <div style={{ marginTop: '8px', fontSize: '13px' }}>
                  <span style={{ fontWeight: 600, color: '#374151' }}>Description:</span>{' '}
                  <span style={{ color: '#6B7280' }}>{emailParsed.description.substring(0, 200)}...</span>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Active Filter Pills (shown outside filter panel) */}
      {!showFilters && activeFilterCount > 0 && (
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '16px', alignItems: 'center' }}>
          <span className="text-sm text-light" style={{ marginRight: '4px' }}>Filters:</span>
          {appliedFilters.price_min && (
            <span style={{
              backgroundColor: '#EFF6FF', color: '#2563EB', borderRadius: '14px',
              padding: '3px 10px', fontSize: '12px', fontWeight: 600,
            }}>
              Min: {formatPrice(Number(appliedFilters.price_min))}
              <span style={{ cursor: 'pointer', marginLeft: '6px' }} onClick={() => {
                setFilters(p => ({ ...p, price_min: '' }));
                setAppliedFilters(p => { const n = { ...p }; delete n.price_min; return n; });
              }}>&times;</span>
            </span>
          )}
          {appliedFilters.price_max && (
            <span style={{
              backgroundColor: '#EFF6FF', color: '#2563EB', borderRadius: '14px',
              padding: '3px 10px', fontSize: '12px', fontWeight: 600,
            }}>
              Max: {formatPrice(Number(appliedFilters.price_max))}
              <span style={{ cursor: 'pointer', marginLeft: '6px' }} onClick={() => {
                setFilters(p => ({ ...p, price_max: '' }));
                setAppliedFilters(p => { const n = { ...p }; delete n.price_max; return n; });
              }}>&times;</span>
            </span>
          )}
          {appliedFilters.location && (
            <span style={{
              backgroundColor: '#F0FDF4', color: '#16A34A', borderRadius: '14px',
              padding: '3px 10px', fontSize: '12px', fontWeight: 600,
            }}>
              {appliedFilters.location}
              <span style={{ cursor: 'pointer', marginLeft: '6px' }} onClick={() => {
                setFilters(p => ({ ...p, location: '' }));
                setAppliedFilters(p => { const n = { ...p }; delete n.location; return n; });
              }}>&times;</span>
            </span>
          )}
          {appliedFilters.category && (
            <span style={{
              backgroundColor: '#FEF3C7', color: '#B45309', borderRadius: '14px',
              padding: '3px 10px', fontSize: '12px', fontWeight: 600,
            }}>
              {appliedFilters.category}
              <span style={{ cursor: 'pointer', marginLeft: '6px' }} onClick={() => {
                setFilters(p => ({ ...p, category: '' }));
                setAppliedFilters(p => { const n = { ...p }; delete n.category; return n; });
              }}>&times;</span>
            </span>
          )}
          {appliedFilters.q && (
            <span style={{
              backgroundColor: '#FFF5F1', color: '#D4532F', borderRadius: '14px',
              padding: '3px 10px', fontSize: '12px', fontWeight: 600,
            }}>
              &ldquo;{appliedFilters.q}&rdquo;
              <span style={{ cursor: 'pointer', marginLeft: '6px' }} onClick={() => {
                setFilters(p => ({ ...p, q: '' }));
                setAppliedFilters(p => { const n = { ...p }; delete n.q; return n; });
              }}>&times;</span>
            </span>
          )}
          <button
            className="btn btn-secondary btn-sm"
            onClick={clearFilters}
            style={{ fontSize: '11px', padding: '2px 8px' }}
          >
            Clear All
          </button>
        </div>
      )}

      {/* Add Site Form */}
      {showAddForm && (
        <div className="card" style={{ marginBottom: '20px' }}>
          <h3 style={{ marginBottom: '16px' }}>Add Broker Site to Monitor</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '12px', alignItems: 'end' }}>
            <div>
              <label className="text-sm" style={{ fontWeight: 600, display: 'block', marginBottom: '4px' }}>
                Site Name
              </label>
              <input
                className="input"
                placeholder={fetchingName ? 'Fetching name...' : 'e.g. NJ Broker Plus'}
                value={newSite.name}
                onChange={(e) => setNewSite({ ...newSite, name: e.target.value })}
              />
            </div>
            <div>
              <label className="text-sm" style={{ fontWeight: 600, display: 'block', marginBottom: '4px' }}>
                Listings Page URL(s) — comma-separate for multiple pages
              </label>
              <input
                className="input"
                placeholder="https://example.com/listings"
                value={newSite.url}
                onChange={(e) => handleUrlChange(e.target.value)}
              />
            </div>
            <div>
              <label className="text-sm" style={{ fontWeight: 600, display: 'block', marginBottom: '4px' }}>
                Link to Contact
              </label>
              <select
                className="input"
                value={newSite.contact_id}
                onChange={(e) => setNewSite({ ...newSite, contact_id: e.target.value })}
              >
                <option value="">— No contact —</option>
                {contacts.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name || c.email}{c.company ? ` (${c.company})` : ''}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-sm" style={{ fontWeight: 600, display: 'block', marginBottom: '4px' }}>
                Check every (hours)
              </label>
              <input
                className="input"
                type="number"
                min={1}
                value={newSite.check_interval_hours}
                onChange={(e) => setNewSite({ ...newSite, check_interval_hours: parseInt(e.target.value) || 24 })}
                style={{ width: '100px' }}
              />
            </div>
          </div>
          <div style={{ marginTop: '14px', display: 'flex', gap: '8px' }}>
            <button className="btn btn-primary" onClick={handleAddSite} disabled={!newSite.url.trim()}>
              Add & Check Now
            </button>
            <button className="btn btn-secondary" onClick={() => setShowAddForm(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* CSV Upload Form */}
      {showCsvUpload && (
        <div className="card" style={{ marginBottom: '20px' }}>
          <h3 style={{ marginBottom: '16px' }}>Upload Broker Sites from CSV</h3>
          <p className="text-sm text-light" style={{ marginBottom: '12px' }}>
            Upload a CSV or Excel file with broker website URLs. The system will auto-detect
            columns for URL, name, scraper type, and check interval. Duplicate URLs will be skipped.
          </p>
          <div style={{
            border: '2px dashed #D1D5DB',
            borderRadius: '8px',
            padding: '24px',
            textAlign: 'center',
            marginBottom: '12px',
            backgroundColor: uploadFile ? '#F0FDF4' : '#F9FAFB',
          }}>
            <input
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={(e) => {
                setUploadFile(e.target.files[0] || null);
                setUploadResult(null);
              }}
            />
            {uploadFile && (
              <div className="text-sm" style={{ color: '#059669', marginTop: '8px' }}>
                Selected: {uploadFile.name}
              </div>
            )}
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              className="btn btn-primary"
              onClick={handleCsvUpload}
              disabled={!uploadFile || uploading}
            >
              {uploading ? 'Uploading & Scraping...' : 'Upload & Add Sites'}
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => { setShowCsvUpload(false); setUploadFile(null); setUploadResult(null); }}
            >
              Cancel
            </button>
          </div>
          {uploadResult && (
            <div style={{
              marginTop: '12px',
              padding: '12px',
              borderRadius: '8px',
              backgroundColor: uploadResult.error ? '#FEF2F2' : '#F0FDF4',
              border: `1px solid ${uploadResult.error ? '#FECACA' : '#BBF7D0'}`,
            }}>
              {uploadResult.error ? (
                <div>
                  <div style={{ color: '#DC2626', fontWeight: 600 }}>{uploadResult.error}</div>
                  {uploadResult.headers && (
                    <div className="text-sm" style={{ marginTop: '4px', color: '#78716C' }}>
                      Detected columns: {uploadResult.headers.join(', ')}
                    </div>
                  )}
                </div>
              ) : (
                <div>
                  <div style={{ color: '#059669', fontWeight: 600, marginBottom: '4px' }}>
                    Upload complete!
                  </div>
                  <div className="text-sm">
                    {uploadResult.created} site{uploadResult.created !== 1 ? 's' : ''} created and scraped
                    {uploadResult.skipped_duplicate > 0 && `, ${uploadResult.skipped_duplicate} duplicate${uploadResult.skipped_duplicate !== 1 ? 's' : ''} skipped`}
                    {uploadResult.skipped_invalid > 0 && `, ${uploadResult.skipped_invalid} invalid row${uploadResult.skipped_invalid !== 1 ? 's' : ''} skipped`}
                  </div>
                  {uploadResult.scrape_results && uploadResult.scrape_results.length > 0 && (
                    <div className="text-sm" style={{ marginTop: '8px' }}>
                      {uploadResult.scrape_results.map((r, i) => (
                        <div key={i} style={{ marginTop: '2px' }}>
                          {r.name || `Site ${r.site_id}`}: {r.error
                            ? <span style={{ color: '#DC2626' }}>{r.error}</span>
                            : <span>{r.new || 0} new listing{(r.new || 0) !== 1 ? 's' : ''} found{r.filtered_out ? `, ${r.filtered_out} filtered by buy box` : ''}</span>
                          }
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Monitored Sites Bar */}
      {sites.length > 0 && (
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '20px' }}>
          <button
            className={`btn btn-sm ${!filterSiteId ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setFilterSiteId(null)}
            style={{ borderRadius: '20px' }}
          >
            All Sites
          </button>
          {sites.map((site) => (
            <button
              key={site.id}
              className={`btn btn-sm ${filterSiteId === site.id ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setFilterSiteId(filterSiteId === site.id ? null : site.id)}
              style={{ borderRadius: '20px', display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              {site.name}
              {site.new_listing_count > 0 && (
                <span style={{
                  backgroundColor: '#F59E0B',
                  color: '#fff',
                  borderRadius: '10px',
                  padding: '0 6px',
                  fontSize: '11px',
                  fontWeight: 700,
                }}>
                  {site.new_listing_count}
                </span>
              )}
            </button>
          ))}
        </div>
      )}

      {/* Sites with errors (show when no listings) */}
      {listings.groups.length === 0 && sites.length > 0 && sites.some(s => s.last_error) && (
        <div className="card" style={{ marginBottom: '16px', padding: '16px', borderLeft: '4px solid #F59E0B' }}>
          <div style={{ fontWeight: 600, marginBottom: '8px', color: '#92400E' }}>
            Some sites had issues scraping:
          </div>
          {sites.filter(s => s.last_error).map(s => (
            <div key={s.id} style={{ fontSize: '13px', color: '#6B7280', marginBottom: '4px' }}>
              <strong>{s.name}:</strong> {s.last_error}
            </div>
          ))}
          <div style={{ fontSize: '13px', color: '#6B7280', marginTop: '8px' }}>
            Many broker sites embed listings from BizBuySell, which blocks automated access.
            Make sure the URL points to the actual listings page (not the homepage).
          </div>
        </div>
      )}

      {/* Listings by Site */}
      {listings.groups.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <p>{sites.length === 0
              ? 'No sites being monitored yet. Add a broker website to get started!'
              : activeFilterCount > 0
                ? 'No listings match your filters. Try broadening your criteria.'
                : showNewOnly
                  ? 'No new listings. Check back later!'
                  : 'No listings found yet. Click "Check Now" on a site to scrape for listings.'
            }</p>
          </div>
        </div>
      ) : (
        listings.groups.map((group) => (
          <div key={group.site.id} style={{ marginBottom: '24px' }}>
            {/* Site Header */}
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '10px',
              padding: '12px 16px',
              backgroundColor: '#F9FAFB',
              borderRadius: '10px',
              border: '1px solid #E5E7EB',
            }}>
              <div>
                <span style={{ fontWeight: 700, fontSize: '16px' }}>{group.site.name}</span>
                {group.site.contact && (
                  <Link
                    to={`/contacts/${group.site.contact.id}`}
                    style={{ marginLeft: '10px', fontSize: '13px', color: '#E8603C' }}
                  >
                    {group.site.contact.name || group.site.contact.email}
                  </Link>
                )}
                <span className="text-sm text-light" style={{ marginLeft: '10px' }}>
                  {group.listings.length} listing{group.listings.length !== 1 ? 's' : ''}
                  {group.site.last_checked_at && (
                    <> &middot; Last checked {new Date(group.site.last_checked_at).toLocaleDateString('en-US', {
                      month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
                    })}</>
                  )}
                </span>
                {group.site.last_error && (
                  <span style={{ marginLeft: '8px', color: '#EF4444', fontSize: '12px' }}>
                    Error: {group.site.last_error.substring(0, 60)}
                  </span>
                )}
              </div>
              <div style={{ display: 'flex', gap: '6px' }}>
                {group.site.new_listing_count > 0 && (
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => handleMarkAllSeen(group.site.id)}
                  >
                    Mark All Seen
                  </button>
                )}
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => handleCheckSite(group.site.id)}
                  disabled={checkingSiteId === group.site.id}
                >
                  {checkingSiteId === group.site.id ? 'Checking...' : 'Check Now'}
                </button>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => handleDeleteSite(group.site.id)}
                  style={{ color: '#EF4444' }}
                >
                  Remove
                </button>
              </div>
            </div>

            {/* Listing Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '12px' }}>
              {group.listings.map((listing) => (
                <div
                  key={listing.id}
                  className="card"
                  style={{
                    border: listing.is_new ? '2px solid #F59E0B' : '1px solid #E5E7EB',
                    position: 'relative',
                    padding: '16px',
                  }}
                >
                  {/* New badge + Source badge */}
                  <div style={{ position: 'absolute', top: '10px', right: '10px', display: 'flex', gap: '4px' }}>
                    {listing.source && listing.source !== 'scraper' && (
                      <span style={{
                        backgroundColor: listing.source === 'email' ? '#DBEAFE' : '#FFF1EC',
                        color: listing.source === 'email' ? '#1D4ED8' : '#6D28D9',
                        fontSize: '10px',
                        fontWeight: 700,
                        padding: '2px 6px',
                        borderRadius: '10px',
                        textTransform: 'uppercase',
                      }}>
                        {listing.source}
                      </span>
                    )}
                    {listing.is_new && (
                      <span style={{
                        backgroundColor: '#F59E0B',
                        color: '#fff',
                        fontSize: '11px',
                        fontWeight: 700,
                        padding: '2px 8px',
                        borderRadius: '10px',
                      }}>
                        NEW
                      </span>
                    )}
                  </div>

                  {/* Image */}
                  {listing.image_url && (
                    <div style={{
                      width: '100%',
                      height: '160px',
                      borderRadius: '8px',
                      overflow: 'hidden',
                      marginBottom: '10px',
                      backgroundColor: '#F3F4F6',
                    }}>
                      <img
                        src={listing.image_url}
                        alt={listing.title}
                        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                        onError={(e) => { e.target.style.display = 'none'; }}
                      />
                    </div>
                  )}

                  {/* Title */}
                  <h4 style={{ margin: '0 0 6px 0', fontSize: '15px', paddingRight: listing.is_new ? '50px' : 0 }}>
                    {listing.url ? (
                      <a href={listing.url} target="_blank" rel="noopener noreferrer" style={{ color: '#111827' }}>
                        {listing.title}
                      </a>
                    ) : (
                      listing.title
                    )}
                  </h4>

                  {/* Price */}
                  {listing.price && (
                    <div style={{ fontSize: '16px', fontWeight: 700, color: '#059669', marginBottom: '6px' }}>
                      {listing.price}
                    </div>
                  )}

                  {/* Financial Metrics */}
                  {(listing.revenue_str || listing.sde_str || listing.ebitda_str || listing.cash_flow_str || listing.net_profit_str) && (
                    <div style={{
                      display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '8px',
                    }}>
                      {listing.revenue_str && (
                        <span style={{ backgroundColor: '#EFF6FF', color: '#2563EB', borderRadius: '6px', padding: '2px 8px', fontSize: '11px', fontWeight: 600 }}>
                          Rev: {listing.revenue_str}
                        </span>
                      )}
                      {listing.sde_str && (
                        <span style={{ backgroundColor: '#F0FDF4', color: '#16A34A', borderRadius: '6px', padding: '2px 8px', fontSize: '11px', fontWeight: 600 }}>
                          SDE: {listing.sde_str}
                        </span>
                      )}
                      {listing.ebitda_str && (
                        <span style={{ backgroundColor: '#FEF3C7', color: '#B45309', borderRadius: '6px', padding: '2px 8px', fontSize: '11px', fontWeight: 600 }}>
                          EBITDA: {listing.ebitda_str}
                        </span>
                      )}
                      {listing.cash_flow_str && (
                        <span style={{ backgroundColor: '#FFF5F1', color: '#D4532F', borderRadius: '6px', padding: '2px 8px', fontSize: '11px', fontWeight: 600 }}>
                          CF: {listing.cash_flow_str}
                        </span>
                      )}
                      {listing.net_profit_str && (
                        <span style={{ backgroundColor: '#FEF2F2', color: '#DC2626', borderRadius: '6px', padding: '2px 8px', fontSize: '11px', fontWeight: 600 }}>
                          Net: {listing.net_profit_str}
                        </span>
                      )}
                    </div>
                  )}

                  {/* Location & Category */}
                  <div className="text-sm text-light" style={{ marginBottom: '6px' }}>
                    {[
                      listing.location,
                      listing.normalized_category && listing.normalized_category !== 'Other'
                        ? listing.normalized_category
                        : listing.category,
                    ].filter(Boolean).join(' · ') || ''}
                  </div>

                  {/* Description */}
                  {listing.description && (
                    <p className="text-sm" style={{ color: '#6B7280', margin: '0 0 10px 0', lineHeight: '1.4' }}>
                      {listing.description.substring(0, 150)}
                      {listing.description.length > 150 && '...'}
                    </p>
                  )}

                  {/* Footer */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 'auto' }}>
                    <span className="text-sm text-light">
                      Found {new Date(listing.first_seen_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                    </span>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      {listing.is_new && (
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleMarkSeen(listing.id)}
                          style={{ fontSize: '12px', padding: '2px 8px' }}
                        >
                          Mark Seen
                        </button>
                      )}
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => setEditingNotes(editingNotes?.listingId === listing.id ? null : { listingId: listing.id, notes: listing.notes || '' })}
                        style={{ fontSize: '12px', padding: '2px 8px' }}
                      >
                        {listing.notes ? 'Notes' : '+ Note'}
                      </button>
                      <button
                        className="btn btn-primary btn-sm"
                        onClick={() => handleTrackDeal(listing)}
                        style={{ fontSize: '12px', padding: '2px 8px' }}
                      >
                        Track Deal
                      </button>
                    </div>
                  </div>

                  {/* Notes editor */}
                  {editingNotes?.listingId === listing.id && (
                    <div style={{ marginTop: '10px', padding: '10px', backgroundColor: '#F9FAFB', borderRadius: '8px' }}>
                      <textarea
                        className="input"
                        rows={2}
                        value={editingNotes.notes}
                        onChange={(e) => setEditingNotes({ ...editingNotes, notes: e.target.value })}
                        placeholder="Add notes about this listing..."
                        style={{ fontSize: '13px', resize: 'vertical', marginBottom: '6px' }}
                      />
                      <div style={{ display: 'flex', gap: '6px' }}>
                        <button className="btn btn-primary btn-sm" onClick={() => handleSaveNotes(listing.id, editingNotes.notes)}>
                          Save
                        </button>
                        <button className="btn btn-secondary btn-sm" onClick={() => setEditingNotes(null)}>
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  );
}

export default Listings;
