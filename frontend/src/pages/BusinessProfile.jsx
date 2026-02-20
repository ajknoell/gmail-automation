import { useState, useEffect } from 'react';
import { getBusinessProfile, updateBusinessProfile } from '../api/client';

function BusinessProfile() {
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

  useEffect(() => { loadProfile(); }, []);

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
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      alert('Save failed: ' + (err.response?.data?.error || err.message));
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
        <h1>Business Profile</h1>
        <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? 'Saving...' : saved ? 'Saved!' : 'Save Profile'}
        </button>
      </div>

      <p style={{ color: '#6B7280', marginBottom: '24px' }}>
        Define what your business does so Veloro can score signal relevance and match opportunities.
      </p>

      {/* Core Identity */}
      <div className="card" style={{ padding: '20px', marginBottom: '20px' }}>
        <h3 style={{ marginBottom: '16px' }}>Identity</h3>
        <div style={{ display: 'grid', gap: '12px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
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
      <div className="card" style={{ padding: '20px', marginBottom: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h3>Capabilities</h3>
          <button className="btn btn-sm btn-secondary" onClick={addCapability}>+ Add Capability</button>
        </div>
        {capabilities.length === 0 ? (
          <p style={{ color: '#6B7280' }}>No capabilities defined yet. Add what services you offer.</p>
        ) : (
          <div style={{ display: 'grid', gap: '12px' }}>
            {capabilities.map((cap, i) => (
              <div key={i} style={{ border: '1px solid #E5E7EB', borderRadius: '8px', padding: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <input className="input" value={cap.name} onChange={e => updateCapability(i, 'name', e.target.value)}
                    placeholder="Capability name (e.g., Salesforce Implementation)"
                    style={{ flex: 1, marginRight: '8px' }} />
                  <button className="btn btn-sm" onClick={() => removeCapability(i)} style={{ color: '#EF4444' }}>Remove</button>
                </div>
                <textarea className="input" rows={2} value={cap.description || ''}
                  onChange={e => updateCapability(i, 'description', e.target.value)}
                  placeholder="Brief description of this capability..." style={{ marginBottom: '8px' }} />
                <input className="input" value={(cap.keywords || []).join(', ')}
                  onChange={e => updateCapability(i, 'keywords', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
                  placeholder="Keywords (comma-separated): salesforce, CRM, implementation, migration" />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Target Market */}
      <div className="card" style={{ padding: '20px', marginBottom: '20px' }}>
        <h3 style={{ marginBottom: '16px' }}>Target Market</h3>
        <div style={{ display: 'grid', gap: '12px' }}>
          <div>
            <label className="label">Industries (comma-separated)</label>
            <input className="input" value={(targetMarket.industries || []).join(', ')}
              onChange={e => updateIndustries(e.target.value)}
              placeholder="Healthcare, Manufacturing, SaaS, Real Estate" />
          </div>
          <div>
            <label className="label">Geographies (comma-separated)</label>
            <input className="input" value={(targetMarket.geographies || []).join(', ')}
              onChange={e => updateGeographies(e.target.value)}
              placeholder="Chicago, Austin, Remote, United States" />
          </div>
          <div>
            <label className="label">Company Sizes</label>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {['1-10', '11-50', '51-200', '201-1000', '1000+'].map(size => (
                <label key={size} style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
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
                    }} />
                  {size}
                </label>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Keywords */}
      <div className="card" style={{ padding: '20px' }}>
        <h3 style={{ marginBottom: '16px' }}>Relevance Keywords</h3>
        <p style={{ color: '#6B7280', fontSize: '0.85em', marginBottom: '12px' }}>
          Keywords used to match signals against your business. Signals containing these keywords score higher for relevance.
        </p>
        <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
          <input className="input" value={newKeyword} onChange={e => setNewKeyword(e.target.value)}
            placeholder="Add keyword..." style={{ maxWidth: '300px' }}
            onKeyDown={e => e.key === 'Enter' && addKeyword()} />
          <button className="btn btn-sm btn-secondary" onClick={addKeyword}>Add</button>
        </div>
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          {keywords.map(kw => (
            <span key={kw} style={{
              display: 'flex', alignItems: 'center', gap: '4px',
              padding: '4px 10px', borderRadius: '16px',
              background: '#EEF2FF', color: '#4338CA', fontSize: '0.85em',
            }}>
              {kw}
              <button onClick={() => removeKeyword(kw)} style={{
                background: 'none', border: 'none', cursor: 'pointer',
                color: '#6366F1', fontWeight: 'bold', padding: 0,
              }}>&times;</button>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

export default BusinessProfile;
