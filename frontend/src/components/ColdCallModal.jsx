import { useState, useEffect, useRef } from 'react';
import { createColdCall, updateColdCall, getColdCallOutcomes } from '../api/client';

const DEFAULT_FORM = {
  call_date: new Date().toISOString().slice(0, 16),
  outcome: 'connected',
  notes: '',
  duration_minutes: '',
};

const FALLBACK_OUTCOMES = [
  { value: 'connected', label: 'Connected' },
  { value: 'voicemail', label: 'Left Voicemail' },
  { value: 'no_answer', label: 'No Answer' },
  { value: 'callback_requested', label: 'Callback Requested' },
  { value: 'not_interested', label: 'Not Interested' },
  { value: 'wrong_number', label: 'Wrong Number' },
  { value: 'other', label: 'Other' },
];

function ColdCallModal({ onClose, onSaved, contactId, campaignId, recipientId, editingCall }) {
  const [form, setForm] = useState(DEFAULT_FORM);
  const [outcomes, setOutcomes] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const mouseDownTarget = useRef(null);

  useEffect(() => {
    getColdCallOutcomes()
      .then((res) => setOutcomes(res.data || []))
      .catch(() => setOutcomes(FALLBACK_OUTCOMES));

    if (editingCall) {
      setForm({
        call_date: editingCall.call_date
          ? editingCall.call_date.slice(0, 16)
          : DEFAULT_FORM.call_date,
        outcome: editingCall.outcome || 'connected',
        notes: editingCall.notes || '',
        duration_minutes: editingCall.duration_minutes ?? '',
      });
    }
  }, [editingCall]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError(null);

    const payload = {
      call_date: form.call_date ? new Date(form.call_date).toISOString() : undefined,
      outcome: form.outcome,
      notes: form.notes,
      duration_minutes: form.duration_minutes ? parseInt(form.duration_minutes) : null,
    };

    try {
      if (editingCall) {
        await updateColdCall(editingCall.id, payload);
      } else {
        await createColdCall({
          ...payload,
          contact_id: contactId || undefined,
          campaign_id: campaignId || undefined,
          recipient_id: recipientId || undefined,
        });
      }
      onSaved();
      onClose();
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to save cold call');
    }
    setSaving(false);
  };

  const handleOverlayMouseDown = (e) => {
    mouseDownTarget.current = e.target;
  };

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget && mouseDownTarget.current === e.currentTarget) {
      onClose();
    }
    mouseDownTarget.current = null;
  };

  return (
    <div className="modal-overlay" onMouseDown={handleOverlayMouseDown} onClick={handleOverlayClick}>
      <div className="modal" style={{ maxWidth: '500px' }}>
        <div className="modal-header">
          <h3 className="modal-title">{editingCall ? 'Edit Cold Call' : 'Log Cold Call'}</h3>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {error && (
              <div style={{
                padding: '0.75rem',
                marginBottom: '1rem',
                borderRadius: '0.375rem',
                background: '#FEF2F2',
                color: '#DC2626',
                fontSize: '0.875rem',
              }}>
                {error}
              </div>
            )}

            <div className="form-group">
              <label className="form-label">Date & Time</label>
              <input
                type="datetime-local"
                className="form-input"
                value={form.call_date}
                onChange={(e) => setForm({ ...form, call_date: e.target.value })}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label">Outcome</label>
              <select
                className="form-input"
                value={form.outcome}
                onChange={(e) => setForm({ ...form, outcome: e.target.value })}
              >
                {outcomes.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Duration (minutes, optional)</label>
              <input
                type="number"
                className="form-input"
                value={form.duration_minutes}
                onChange={(e) => setForm({ ...form, duration_minutes: e.target.value })}
                min="0"
                placeholder="e.g. 5"
              />
            </div>

            <div className="form-group">
              <label className="form-label">Notes</label>
              <textarea
                className="form-textarea"
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                placeholder="Key points from the call..."
                rows={4}
              />
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Saving...' : (editingCall ? 'Update' : 'Log Call')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default ColdCallModal;
