import { useState, useEffect } from 'react';
import { getBusinessProfile, updateBusinessProfile } from '../api/client';
import { useToast } from '../components/Toast';

function BusinessProfile() {
  const showToast = useToast();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // Form state
  const [companyName, setCompanyName] = useState('');
  const [domain, setDomain] = useState('');
  const [tagline, setTagline] = useState('');
  const [description, setDescription] = useState('');
  const [capabilities, setCapabilities] = useState([]);
  const [targetMarket, setTargetMarket] = useState({ industries: [], company_sizes: [], geographies: [] });
  const [keywords, setKeywords] = useState([]);
  const [newKeyword, setNewKeyword] = useState('');

  useEffect(() => {
    loadProfile();
    const handleWsChange = () => loadProfile();
    window.addEventListener('workspace-changed', handleWsChange);
    return () => window.removeEventListener('workspace-changed', handleWsChange);
  }, []);

  const loadProfile = async () => {
    setLoading(true);
    try {
      const res = await getBusinessProfile();
      const p = res.data;
      setProfile(p);
      setCompanyName(p.company_name || '');
      setDomain(p.domain || '');
      setTagline(p.tagline || '');
      setDescription(p.description || '');
      setCapabilities(p.capabilities || []);
      setTargetMarket(p.target_market || { industries: [], company_sizes: [], geographies: [] });
      setKeywords(p.keywords || []);
    } catch (err) {
      console.error('Profile load error:', err);
    }
    setLoading(false);
  };

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    try {
      await updateBusinessProfile({
        company_name: companyName,
        domain,
        tagline,
        description,
        capabilities,
        target_market: targetMarket,
        keywords,
      });
      showToast('Profile saved', 'success');
    } catch (err) {
      showToast('Save failed: ' + (err.response?.data?.error || err.message), 'error');
    }
    setSaving(false);
  };

  const addCapability = () => {
    setCapabilities([...capabilities, { name: '', description: '', keywords: [] }]);
  };

  const updateCapability = (index, field, value) => {
    const updated = [...capabilities];
    updated[index] = { ...updated[index], [field]: value };
    setCapabilities(updated);
  };

  const removeCapability = (index) => {
    setCapabilities(capabilities.filter((_, i) => i !== index));
  };

  const addKeyword = () => {
    const kw = newKeyword.trim();
    if (kw && !keywords.includes(kw)) {
      setKeywords([...keywords, kw]);
      setNewKeyword('');
    }
  };

  const removeKeyword = (kw) => {
    setKeywords(keywords.filter(k => k !== kw));
  };

  const updateIndustries = (value) => {
    setTargetMarket({
      ...targetMarket,
      industries: value.split(',').map(s => s.trim()).filter(Boolean),
    });
  };

  const updateGeographies = (value) => {
    setTargetMarket({
      ...targetMarket,
      geographies: value.split(',').map(s => s.trim()).filter(Boolean),
    });
  };

  if (loading) return <div className="page"><p>Loading...</p></div>;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Business Profile</h1>
          <p style={{ color: 'var(--text-light)', fontSize: '0.875rem', marginTop: '0.25rem' }}>
            Define what your business does so Veloro can score signal relevance and match opportunities.
          </p>
        </div>
        <button
          className={`btn ${saved ? 'btn-success' : 'btn-primary'}`}
          onClick={handleSave}
          disabled={saving}
        >
          {saving ? 'Saving...' : saved ? 'Saved!' : 'Save Profile'}
        </button>
      </div>

      <div style={{ display: 'grid', gap: '1.25rem' }}>
        {/* Core Identity */}
        <div className="card">
          <div className="card-section-title">Identity</div>
          <div style={{ display: 'grid', gap: '1rem' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
              <div>
                <label className="label">Company Name</label>
                <input className="input" value={companyName} onChange={e => setCompanyName(e.target.value)}
                  placeholder="Acme Consulting" />
              </div>
              <div>
                <label className="label">Domain</label>
                <input className="input" value={domain} onChange={e => setDomain(e.target.value)}
                  placeholder="acmeconsulting.com" />
              </div>
            </div>
            <div>
              <label className="label">Tagline</label>
              <input className="input" value={tagline} onChange={e => setTagline(e.target.value)}
                placeholder="We help companies scale their Salesforce operations" />
            </div>
            <div>
              <label className="label">Description</label>
              <textarea className="input" rows={3} value={description} onChange={e => setDescription(e.target.value)}
                placeholder="Brief description of what your business does and who you serve..." />
            </div>
          </div>
        </div>

        {/* Capabilities */}
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <div className="card-section-title" style={{ marginBottom: 0 }}>Capabilities</div>
            <button className="btn btn-sm btn-secondary" onClick={addCapability}>+ Add</button>
          </div>
          {capabilities.length === 0 ? (
            <p style={{ color: 'var(--text-light)', fontSize: '0.875rem' }}>
              No capabilities defined yet. Add what services you offer.
            </p>
          ) : (
            <div style={{ display: 'grid', gap: '0.75rem' }}>
              {capabilities.map((cap, i) => (
                <div key={i} style={{
                  border: '1px solid var(--border)',
                  borderRadius: '0.5rem',
                  padding: '0.875rem',
                  background: 'var(--bg)',
                }}>
                  <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem' }}>
                    <input className="input" value={cap.name} onChange={e => updateCapability(i, 'name', e.target.value)}
                      placeholder="Capability name (e.g., Salesforce Implementation)"
                      style={{ flex: 1 }} />
                    <button className="btn btn-sm" onClick={() => removeCapability(i)}
                      style={{ color: 'var(--error)', flexShrink: 0 }}>Remove</button>
                  </div>
                  <textarea className="input" rows={2} value={cap.description || ''}
                    onChange={e => updateCapability(i, 'description', e.target.value)}
                    placeholder="Brief description of this capability..."
                    style={{ marginBottom: '0.5rem' }} />
                  <input className="input" value={(cap.keywords || []).join(', ')}
                    onChange={e => updateCapability(i, 'keywords', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
                    placeholder="Keywords (comma-separated): salesforce, CRM, implementation" />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Target Market */}
        <div className="card">
          <div className="card-section-title">Target Market</div>
          <div style={{ display: 'grid', gap: '1rem' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
              <div>
                <label className="label">Industries (comma-separated)</label>
                <input className="input" value={(targetMarket.industries || []).join(', ')}
                  onChange={e => updateIndustries(e.target.value)}
                  placeholder="Healthcare, Manufacturing, SaaS" />
              </div>
              <div>
                <label className="label">Geographies (comma-separated)</label>
                <input className="input" value={(targetMarket.geographies || []).join(', ')}
                  onChange={e => updateGeographies(e.target.value)}
                  placeholder="Chicago, Austin, Remote" />
              </div>
            </div>
            <div>
              <label className="label">Company Sizes</label>
              <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginTop: '0.25rem' }}>
                {['1-10', '11-50', '51-200', '201-1000', '1000+'].map(size => (
                  <label key={size} style={{
                    display: 'flex', alignItems: 'center', gap: '0.375rem',
                    cursor: 'pointer', fontSize: '0.875rem', color: 'var(--text)',
                    padding: '0.375rem 0.625rem',
                    borderRadius: '0.375rem',
                    border: '1px solid var(--border)',
                    background: (targetMarket.company_sizes || []).includes(size) ? 'rgba(79, 70, 229, 0.06)' : 'transparent',
                  }}>
                    <input type="checkbox"
                      checked={(targetMarket.company_sizes || []).includes(size)}
                      onChange={e => {
                        const sizes = targetMarket.company_sizes || [];
                        setTargetMarket({
                          ...targetMarket,
                          company_sizes: e.target.checked
                            ? [...sizes, size]
                            : sizes.filter(s => s !== size),
                        });
                      }}
                      style={{ accentColor: 'var(--primary)' }}
                    />
                    {size}
                  </label>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Keywords */}
        <div className="card">
          <div className="card-section-title">Relevance Keywords</div>
          <p style={{ color: 'var(--text-light)', fontSize: '0.8125rem', marginBottom: '0.75rem', marginTop: '-0.5rem' }}>
            Signals containing these keywords score higher for relevance.
          </p>
          <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem' }}>
            <input className="input" value={newKeyword} onChange={e => setNewKeyword(e.target.value)}
              placeholder="Add keyword..." style={{ maxWidth: '280px' }}
              onKeyDown={e => e.key === 'Enter' && addKeyword()} />
            <button className="btn btn-sm btn-secondary" onClick={addKeyword}>Add</button>
          </div>
          {keywords.length > 0 && (
            <div style={{ display: 'flex', gap: '0.375rem', flexWrap: 'wrap' }}>
              {keywords.map(kw => (
                <span key={kw} style={{
                  display: 'inline-flex', alignItems: 'center', gap: '0.25rem',
                  padding: '0.25rem 0.625rem', borderRadius: '9999px',
                  background: 'rgba(79, 70, 229, 0.08)', color: 'var(--primary)',
                  fontSize: '0.8125rem', fontWeight: 500,
                }}>
                  {kw}
                  <button onClick={() => removeKeyword(kw)} style={{
                    background: 'none', border: 'none', cursor: 'pointer',
                    color: 'var(--primary)', fontWeight: 'bold', padding: 0,
                    fontSize: '0.9em', lineHeight: 1, marginLeft: '0.125rem',
                  }}>&times;</button>
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default BusinessProfile;
