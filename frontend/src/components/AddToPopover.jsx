import { useState, useEffect, useRef } from 'react';

export default function AddToPopover({
  place,
  campaigns,
  position,
  onAddToPipeline,
  onAddToOutreach,
  onClose,
}) {
  const [action, setAction] = useState('pipeline');
  const [email, setEmail] = useState('');
  const [campaignId, setCampaignId] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const popoverRef = useRef(null);

  // Close on outside click and Escape
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target)) {
        onClose();
      }
    };
    const handleEscape = (e) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [onClose]);

  // Flip popover upward if it would go below viewport
  useEffect(() => {
    if (popoverRef.current) {
      const rect = popoverRef.current.getBoundingClientRect();
      if (rect.bottom > window.innerHeight) {
        popoverRef.current.style.top = 'auto';
        popoverRef.current.style.bottom = `${window.innerHeight - position.top + 8}px`;
      }
    }
  }, [position, action]);

  const handleSubmit = async () => {
    setSubmitting(true);
    setResult(null);

    if (action === 'pipeline') {
      await onAddToPipeline(place);
      setSubmitting(false);
      return;
    }

    if (!email.trim()) {
      setResult({ type: 'error', message: 'Email is required.' });
      setSubmitting(false);
      return;
    }
    if (action === 'recipient' && !campaignId) {
      setResult({ type: 'error', message: 'Please select a campaign.' });
      setSubmitting(false);
      return;
    }

    const res = await onAddToOutreach(place, { email, action, campaignId });
    setResult(res);
    setSubmitting(false);
  };

  const options = [
    { value: 'pipeline', label: 'Pipeline', desc: 'Enrich & find email' },
    { value: 'contact', label: 'Contact', desc: 'Add with email' },
    { value: 'recipient', label: 'Campaign Recipient', desc: 'Add to campaign' },
  ];

  return (
    <div
      ref={popoverRef}
      onClick={(e) => e.stopPropagation()}
      style={{
        position: 'fixed',
        top: position.top,
        right: position.right,
        zIndex: 10000,
        width: '260px',
        background: '#fff',
        border: '1px solid #E5E7EB',
        borderRadius: '0.5rem',
        boxShadow: '0 10px 25px rgba(0,0,0,0.15)',
        fontSize: '0.8rem',
      }}
    >
      {/* Header */}
      <div style={{
        padding: '0.5rem 0.75rem',
        borderBottom: '1px solid #F3F4F6',
        fontWeight: 600,
        fontSize: '0.8rem',
        color: '#374151',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      }}>
        Add &ldquo;{place.name}&rdquo;
      </div>

      {/* Action options */}
      <div style={{ padding: '0.5rem 0.75rem' }}>
        {options.map((opt) => (
          <label key={opt.value} style={{
            display: 'flex', alignItems: 'center', gap: '0.4rem',
            padding: '0.3rem 0', cursor: 'pointer', fontSize: '0.8rem',
          }}>
            <input
              type="radio"
              name="popover-action"
              value={opt.value}
              checked={action === opt.value}
              onChange={() => { setAction(opt.value); setResult(null); }}
            />
            <span style={{ fontWeight: 500 }}>{opt.label}</span>
            <span style={{ color: '#9CA3AF', fontSize: '0.7rem' }}>{opt.desc}</span>
          </label>
        ))}
      </div>

      {/* Conditional fields */}
      {action !== 'pipeline' && (
        <div style={{ padding: '0 0.75rem 0.5rem', borderTop: '1px solid #F3F4F6' }}>
          <div style={{ marginTop: '0.5rem' }}>
            <label style={{ display: 'block', fontWeight: 500, fontSize: '0.75rem', marginBottom: '0.2rem' }}>
              Email <span style={{ color: '#EF4444' }}>*</span>
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="business@example.com"
              style={{
                width: '100%', padding: '0.35rem 0.5rem',
                border: '1px solid #D1D5DB', borderRadius: '0.375rem',
                fontSize: '0.8rem', boxSizing: 'border-box',
              }}
            />
          </div>

          {action === 'recipient' && (
            <div style={{ marginTop: '0.4rem' }}>
              <label style={{ display: 'block', fontWeight: 500, fontSize: '0.75rem', marginBottom: '0.2rem' }}>
                Campaign
              </label>
              <select
                value={campaignId}
                onChange={(e) => setCampaignId(e.target.value)}
                style={{
                  width: '100%', padding: '0.35rem 0.5rem',
                  border: '1px solid #D1D5DB', borderRadius: '0.375rem',
                  fontSize: '0.8rem', background: '#fff', boxSizing: 'border-box',
                }}
              >
                <option value="">Select a campaign...</option>
                {campaigns.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
          )}
        </div>
      )}

      {/* Inline result feedback */}
      {result && (
        <div style={{
          padding: '0.35rem 0.75rem', margin: '0 0.5rem 0.4rem',
          borderRadius: '0.25rem', fontSize: '0.75rem',
          background: result.type === 'success' ? '#ECFDF5' : '#FEF2F2',
          color: result.type === 'success' ? '#065F46' : '#991B1B',
        }}>
          {result.message}
        </div>
      )}

      {/* Footer actions */}
      <div style={{
        padding: '0.4rem 0.75rem', borderTop: '1px solid #F3F4F6',
        display: 'flex', justifyContent: 'flex-end', gap: '0.35rem',
      }}>
        <button onClick={onClose} style={{
          padding: '0.3rem 0.6rem', border: '1px solid #D1D5DB',
          borderRadius: '0.375rem', background: '#fff',
          fontSize: '0.75rem', cursor: 'pointer',
        }}>
          Cancel
        </button>
        <button
          onClick={handleSubmit}
          disabled={submitting}
          style={{
            padding: '0.3rem 0.6rem',
            background: submitting ? '#9CA3AF' : '#3B82F6',
            color: '#fff', border: 'none', borderRadius: '0.375rem',
            fontWeight: 600, fontSize: '0.75rem',
            cursor: submitting ? 'not-allowed' : 'pointer',
          }}
        >
          {submitting
            ? 'Adding...'
            : action === 'pipeline'
              ? 'Add to Pipeline'
              : 'Add to Outreach'}
        </button>
      </div>
    </div>
  );
}
