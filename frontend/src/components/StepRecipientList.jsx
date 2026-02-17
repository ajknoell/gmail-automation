import { useState, useEffect } from 'react';
import {
  getStepRecipients,
  updateStepRecipient,
  regenerateStepRecipient,
} from '../api/client';

function StepRecipientList({ campaignId, stepId, stepStatus, onReload }) {
  const [recipients, setRecipients] = useState([]);
  const [loading, setLoading] = useState(false);
  const [previewId, setPreviewId] = useState(null);
  const [regeneratingId, setRegeneratingId] = useState(null);

  useEffect(() => {
    loadRecipients();
  }, [stepId]);

  const loadRecipients = async () => {
    setLoading(true);
    try {
      const res = await getStepRecipients(campaignId, stepId);
      setRecipients(res.data);
    } catch (error) {
      console.error('Failed to load step recipients:', error);
    }
    setLoading(false);
  };

  const handleRegenerate = async (srId) => {
    setRegeneratingId(srId);
    try {
      const res = await regenerateStepRecipient(campaignId, stepId, srId);
      setRecipients((prev) => prev.map((r) => (r.id === srId ? res.data : r)));
      if (onReload) onReload();
    } catch (error) {
      alert('Failed to regenerate: ' + (error.response?.data?.error || error.message));
    }
    setRegeneratingId(null);
  };

  const handleApprove = async (srId, approved) => {
    try {
      const res = await updateStepRecipient(campaignId, stepId, srId, { approved });
      setRecipients((prev) => prev.map((r) => (r.id === srId ? res.data : r)));
    } catch (error) {
      alert('Failed to update approval');
    }
  };

  if (loading) {
    return <div style={{ padding: '1rem', color: '#6B7280', fontSize: '0.85rem' }}>Loading recipients...</div>;
  }

  if (recipients.length === 0) {
    return <div style={{ padding: '1rem', color: '#6B7280', fontSize: '0.85rem' }}>No recipients for this step.</div>;
  }

  const readyCount = recipients.filter((r) => r.status === 'ready' || r.status === 'approved').length;
  const sentCount = recipients.filter((r) => r.status === 'sent').length;
  const skippedCount = recipients.filter((r) => r.status === 'skipped').length;

  const previewRecipient = previewId ? recipients.find((r) => r.id === previewId) : null;

  return (
    <div style={{ marginTop: '1rem' }}>
      <div style={{ fontSize: '0.8rem', color: '#6B7280', marginBottom: '0.5rem' }}>
        {recipients.length} recipients | {readyCount} ready | {sentCount} sent | {skippedCount} skipped
      </div>

      <div style={{ overflowX: 'auto', maxHeight: '400px', overflowY: 'auto' }}>
        <table className="table" style={{ fontSize: '0.85rem' }}>
          <thead>
            <tr>
              <th>Email</th>
              <th>Name</th>
              <th>Status</th>
              <th>Approved</th>
              <th>Preview</th>
              {stepStatus !== 'completed' && <th>Actions</th>}
            </tr>
          </thead>
          <tbody>
            {recipients.map((sr) => (
              <tr key={sr.id}>
                <td>{sr.recipient_email}</td>
                <td>{sr.recipient_name || '-'}</td>
                <td>
                  <span className={`badge badge-${sr.status}`} style={{ fontSize: '0.7rem' }}>
                    {sr.status}
                  </span>
                  {sr.skip_reason && (
                    <span style={{ fontSize: '0.7rem', color: '#9CA3AF', marginLeft: '0.25rem' }}>
                      ({sr.skip_reason})
                    </span>
                  )}
                </td>
                <td>
                  {sr.personalized_body && stepStatus !== 'completed' ? (
                    <button
                      className={`btn btn-sm ${sr.approved ? 'btn-success' : 'btn-secondary'}`}
                      onClick={() => handleApprove(sr.id, !sr.approved)}
                      style={{ padding: '0.15rem 0.4rem', fontSize: '0.75rem' }}
                    >
                      {sr.approved ? 'Yes' : 'Approve'}
                    </button>
                  ) : sr.approved ? (
                    <span style={{ color: '#10B981', fontSize: '0.8rem' }}>Yes</span>
                  ) : (
                    <span style={{ color: '#9CA3AF' }}>-</span>
                  )}
                </td>
                <td>
                  {sr.personalized_body ? (
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => setPreviewId(sr.id)}
                      style={{ padding: '0.15rem 0.4rem', fontSize: '0.75rem' }}
                    >
                      View
                    </button>
                  ) : (
                    <span style={{ color: '#9CA3AF' }}>-</span>
                  )}
                </td>
                {stepStatus !== 'completed' && (
                  <td>
                    {sr.personalized_body && (
                      <button
                        className="btn btn-sm"
                        onClick={() => handleRegenerate(sr.id)}
                        disabled={regeneratingId === sr.id}
                        style={{ padding: '0.15rem 0.4rem', fontSize: '0.75rem', background: '#F3F4F6', border: '1px solid #D1D5DB' }}
                      >
                        {regeneratingId === sr.id ? '...' : 'Regen'}
                      </button>
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Preview Modal */}
      {previewRecipient && (
        <div
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 1000, padding: '2rem',
          }}
          onClick={(e) => { if (e.target === e.currentTarget) setPreviewId(null); }}
        >
          <div style={{
            background: '#fff', borderRadius: '0.75rem', width: '100%', maxWidth: '600px',
            maxHeight: '80vh', display: 'flex', flexDirection: 'column',
            boxShadow: '0 25px 50px rgba(0,0,0,0.25)',
          }}>
            <div style={{
              padding: '1rem 1.5rem', borderBottom: '1px solid #E5E7EB',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            }}>
              <div>
                <strong>{previewRecipient.recipient_name || previewRecipient.recipient_email}</strong>
                {previewRecipient.recipient_company && (
                  <span style={{ color: '#6B7280', marginLeft: '0.5rem' }}>
                    ({previewRecipient.recipient_company})
                  </span>
                )}
              </div>
              <button
                onClick={() => setPreviewId(null)}
                style={{ background: 'none', border: 'none', fontSize: '1.5rem', color: '#9CA3AF', cursor: 'pointer' }}
              >
                &times;
              </button>
            </div>
            <div style={{ overflow: 'auto', padding: '1.5rem' }}>
              <div style={{ marginBottom: '0.75rem' }}>
                <label style={{ fontWeight: 600, fontSize: '0.85rem', color: '#374151' }}>Subject</label>
                <div style={{ fontSize: '0.95rem' }}>{previewRecipient.personalized_subject}</div>
              </div>
              <hr style={{ margin: '0 0 0.75rem 0', border: 'none', borderTop: '1px solid #E5E7EB' }} />
              <div
                style={{ lineHeight: '1.7', fontSize: '0.95rem' }}
                dangerouslySetInnerHTML={{ __html: previewRecipient.personalized_body }}
              />
              {previewRecipient.web_research_results && (
                <details style={{ marginTop: '1rem', fontSize: '0.8rem', color: '#6B7280' }}>
                  <summary style={{ cursor: 'pointer' }}>Web Research Data</summary>
                  <pre style={{ whiteSpace: 'pre-wrap', background: '#F9FAFB', padding: '0.5rem', borderRadius: '0.25rem', marginTop: '0.5rem' }}>
                    {previewRecipient.web_research_results}
                  </pre>
                </details>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default StepRecipientList;
