import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  getContact,
  updateContact,
  getContactStatuses,
  getTags,
  addTagToContact,
  removeTagFromContact,
  deleteColdCall,
} from '../api/client';
import ColdCallModal from '../components/ColdCallModal';

function ContactDetail() {
  const { id } = useParams();
  const [contact, setContact] = useState(null);
  const [emailHistory, setEmailHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [notes, setNotes] = useState('');
  const [savingNotes, setSavingNotes] = useState(false);
  const [notesSaved, setNotesSaved] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState({ name: '', company: '', website: '' });
  const [savingEdit, setSavingEdit] = useState(false);
  const [statuses, setStatuses] = useState([]);
  const [allTags, setAllTags] = useState([]);
  const [newTagName, setNewTagName] = useState('');
  const [followUpDate, setFollowUpDate] = useState('');
  const [followUpNote, setFollowUpNote] = useState('');
  const [savingFollowUp, setSavingFollowUp] = useState(false);
  const [coldCalls, setColdCalls] = useState([]);
  const [showColdCallModal, setShowColdCallModal] = useState(false);
  const [editingColdCall, setEditingColdCall] = useState(null);

  useEffect(() => {
    loadContact();
    getContactStatuses().then((res) => setStatuses(res.data || [])).catch(() => {});
    getTags().then((res) => setAllTags(res.data || [])).catch(() => {});
    const handleWsChange = () => loadContact();
    window.addEventListener('workspace-changed', handleWsChange);
    return () => window.removeEventListener('workspace-changed', handleWsChange);
  }, [id]);

  const loadContact = async () => {
    setLoading(true);
    try {
      const res = await getContact(id);
      setContact(res.data.contact);
      setEmailHistory(res.data.email_history || []);
      setColdCalls(res.data.cold_calls || []);
      setNotes(res.data.contact.notes || '');
      setFollowUpDate(res.data.contact.follow_up_date || '');
      setFollowUpNote(res.data.contact.follow_up_note || '');
      setEditForm({
        name: res.data.contact.name || '',
        company: res.data.contact.company || '',
        website: res.data.contact.website || '',
      });
    } catch {
      setContact(null);
    }
    setLoading(false);
  };

  const handleSaveNotes = async () => {
    setSavingNotes(true);
    try {
      const res = await updateContact(id, { notes });
      setContact(res.data);
      setNotesSaved(true);
      setTimeout(() => setNotesSaved(false), 2000);
    } catch {}
    setSavingNotes(false);
  };

  const handleSaveEdit = async () => {
    setSavingEdit(true);
    try {
      const res = await updateContact(id, editForm);
      setContact(res.data);
      setEditing(false);
    } catch {}
    setSavingEdit(false);
  };

  const handleStatusChange = async (newStatus) => {
    try {
      const res = await updateContact(id, { status: newStatus });
      setContact(res.data);
    } catch {}
  };

  const handleAddTag = async (tagName) => {
    if (!tagName.trim()) return;
    try {
      const res = await addTagToContact(id, { tag_name: tagName.trim() });
      setContact(res.data);
      setNewTagName('');
      // Refresh all tags in case a new one was created
      getTags().then((r) => setAllTags(r.data || [])).catch(() => {});
    } catch {}
  };

  const handleRemoveTag = async (tagId) => {
    try {
      const res = await removeTagFromContact(id, tagId);
      setContact(res.data);
    } catch {}
  };

  const handleSaveFollowUp = async () => {
    setSavingFollowUp(true);
    try {
      const res = await updateContact(id, {
        follow_up_date: followUpDate || null,
        follow_up_note: followUpNote || null,
      });
      setContact(res.data);
    } catch {}
    setSavingFollowUp(false);
  };

  const handleClearFollowUp = async () => {
    setSavingFollowUp(true);
    try {
      const res = await updateContact(id, { follow_up_date: null, follow_up_note: null });
      setContact(res.data);
      setFollowUpDate('');
      setFollowUpNote('');
    } catch {}
    setSavingFollowUp(false);
  };

  const formatDate = (iso) => {
    if (!iso) return '-';
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
    });
  };

  const formatDateTime = (iso) => {
    if (!iso) return '-';
    return new Date(iso).toLocaleString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit',
    });
  };

  if (loading) return <div><p>Loading contact...</p></div>;

  if (!contact) {
    return (
      <div>
        <h1>Contact not found</h1>
        <Link to="/contacts" className="btn btn-secondary">Back to Contacts</Link>
      </div>
    );
  }

  // Tags the contact doesn't have yet
  const availableTags = allTags.filter(
    (t) => !(contact.tags || []).find((ct) => ct.id === t.id)
  );

  return (
    <div>
      <Link to="/contacts" style={{ color: '#6B7280', textDecoration: 'none', fontSize: '0.85rem' }}>
        &larr; Back to Contacts
      </Link>

      <div className="grid grid-2 mt-4">
        {/* Left: Contact Info */}
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <h3 className="card-title mb-2">Contact Info</h3>
            {!editing && (
              <button
                className="btn btn-secondary"
                onClick={() => setEditing(true)}
                style={{ padding: '0.25rem 0.75rem', fontSize: '0.8rem' }}
              >
                Edit
              </button>
            )}
          </div>

          {editing ? (
            <div>
              <div className="form-group">
                <label className="form-label">Name</label>
                <input type="text" className="form-input" value={editForm.name}
                  onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} />
              </div>
              <div className="form-group">
                <label className="form-label">Company</label>
                <input type="text" className="form-input" value={editForm.company}
                  onChange={(e) => setEditForm({ ...editForm, company: e.target.value })} />
              </div>
              <div className="form-group">
                <label className="form-label">Website</label>
                <input type="text" className="form-input" value={editForm.website}
                  onChange={(e) => setEditForm({ ...editForm, website: e.target.value })} />
              </div>
              <div className="flex gap-2">
                <button className="btn btn-primary" onClick={handleSaveEdit} disabled={savingEdit}>
                  {savingEdit ? 'Saving...' : 'Save'}
                </button>
                <button className="btn btn-secondary" onClick={() => {
                  setEditing(false);
                  setEditForm({ name: contact.name || '', company: contact.company || '', website: contact.website || '' });
                }}>Cancel</button>
              </div>
            </div>
          ) : (
            <div>
              <div style={{ marginBottom: '1rem' }}>
                <div style={{ fontSize: '1.25rem', fontWeight: 600 }}>{contact.name || 'Unknown'}</div>
                <div style={{ color: '#6B7280', fontSize: '0.9rem' }}>{contact.email}</div>
              </div>

              {contact.company && (
                <div style={{ marginBottom: '0.5rem' }}>
                  <span style={{ color: '#9CA3AF', fontSize: '0.8rem' }}>Company:</span>{' '}
                  <span style={{ fontWeight: 500 }}>{contact.company}</span>
                </div>
              )}

              {contact.website && (
                <div style={{ marginBottom: '0.5rem' }}>
                  <span style={{ color: '#9CA3AF', fontSize: '0.8rem' }}>Website:</span>{' '}
                  <a href={contact.website.startsWith('http') ? contact.website : `https://${contact.website}`}
                    target="_blank" rel="noopener noreferrer" style={{ color: '#3B82F6' }}>
                    {contact.website}
                  </a>
                </div>
              )}
            </div>
          )}

          {/* Status */}
          <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid #E5E7EB' }}>
            <div style={{ fontSize: '0.75rem', color: '#9CA3AF', marginBottom: '0.25rem' }}>Status</div>
            <select
              value={contact.status || 'new'}
              onChange={(e) => handleStatusChange(e.target.value)}
              style={{
                padding: '0.35rem 0.5rem',
                borderRadius: '0.375rem',
                border: '1px solid #D1D5DB',
                fontSize: '0.85rem',
                fontWeight: 500,
                color: contact.status_color,
                cursor: 'pointer',
              }}
            >
              {statuses.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>

          {/* Tags */}
          <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid #E5E7EB' }}>
            <div style={{ fontSize: '0.75rem', color: '#9CA3AF', marginBottom: '0.5rem' }}>Tags</div>
            <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
              {(contact.tags || []).map((t) => (
                <span
                  key={t.id}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.25rem',
                    padding: '0.15rem 0.5rem',
                    borderRadius: '9999px',
                    fontSize: '0.75rem',
                    fontWeight: 500,
                    backgroundColor: t.color + '20',
                    color: t.color,
                    border: `1px solid ${t.color}40`,
                  }}
                >
                  {t.name}
                  <button
                    onClick={() => handleRemoveTag(t.id)}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: t.color,
                      cursor: 'pointer',
                      padding: 0,
                      fontSize: '0.85rem',
                      lineHeight: 1,
                      marginLeft: '0.1rem',
                    }}
                    title="Remove tag"
                  >
                    &times;
                  </button>
                </span>
              ))}
            </div>
            <div style={{ display: 'flex', gap: '0.35rem', alignItems: 'center' }}>
              <input
                type="text"
                className="form-input"
                value={newTagName}
                onChange={(e) => setNewTagName(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleAddTag(newTagName); }}
                placeholder="Add tag..."
                list="available-tags"
                style={{ flex: 1, padding: '0.25rem 0.5rem', fontSize: '0.8rem' }}
              />
              <datalist id="available-tags">
                {availableTags.map((t) => (
                  <option key={t.id} value={t.name} />
                ))}
              </datalist>
              <button
                className="btn btn-secondary"
                onClick={() => handleAddTag(newTagName)}
                style={{ padding: '0.25rem 0.5rem', fontSize: '0.8rem' }}
              >
                Add
              </button>
            </div>
          </div>

          {/* Stats */}
          <div
            style={{
              marginTop: '1rem',
              paddingTop: '1rem',
              borderTop: '1px solid #E5E7EB',
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: '0.75rem',
            }}
          >
            <div>
              <div style={{ fontSize: '0.75rem', color: '#9CA3AF' }}>First Contacted</div>
              <div style={{ fontWeight: 500, fontSize: '0.9rem' }}>{formatDate(contact.first_contacted_at)}</div>
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: '#9CA3AF' }}>Last Contacted</div>
              <div style={{ fontWeight: 500, fontSize: '0.9rem' }}>{formatDate(contact.last_contacted_at)}</div>
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: '#9CA3AF' }}>Emails Sent</div>
              <div style={{ fontWeight: 500, fontSize: '0.9rem' }}>{contact.total_emails_sent}</div>
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: '#9CA3AF' }}>Replied</div>
              <div style={{ fontWeight: 500, fontSize: '0.9rem' }}>
                {contact.last_replied_at ? (
                  <span style={{ color: '#10B981' }}>Yes ({formatDate(contact.last_replied_at)})</span>
                ) : (
                  <span style={{ color: '#9CA3AF' }}>Not yet</span>
                )}
              </div>
            </div>
          </div>

          {/* Follow-Up */}
          <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid #E5E7EB' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <div style={{ fontSize: '0.75rem', color: '#9CA3AF' }}>Follow-Up</div>
              {contact.follow_up_date && (
                <button
                  onClick={handleClearFollowUp}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#EF4444',
                    fontSize: '0.75rem',
                    cursor: 'pointer',
                    padding: 0,
                  }}
                >
                  Clear
                </button>
              )}
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-end', flexWrap: 'wrap' }}>
              <div>
                <label style={{ fontSize: '0.7rem', color: '#6B7280', display: 'block', marginBottom: '0.15rem' }}>Date</label>
                <input
                  type="date"
                  className="form-input"
                  value={followUpDate}
                  onChange={(e) => setFollowUpDate(e.target.value)}
                  style={{ padding: '0.25rem 0.4rem', fontSize: '0.8rem' }}
                />
              </div>
              <div style={{ flex: 1, minWidth: '120px' }}>
                <label style={{ fontSize: '0.7rem', color: '#6B7280', display: 'block', marginBottom: '0.15rem' }}>Note</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. Check back on proposal"
                  value={followUpNote}
                  onChange={(e) => setFollowUpNote(e.target.value)}
                  style={{ padding: '0.25rem 0.4rem', fontSize: '0.8rem' }}
                />
              </div>
              <button
                className="btn btn-primary"
                onClick={handleSaveFollowUp}
                disabled={savingFollowUp}
                style={{ padding: '0.25rem 0.6rem', fontSize: '0.8rem' }}
              >
                {savingFollowUp ? 'Saving...' : 'Save'}
              </button>
            </div>
            {contact.follow_up_date && (
              <div style={{ marginTop: '0.5rem', fontSize: '0.8rem' }}>
                <span style={{
                  color: new Date(contact.follow_up_date + 'T00:00:00') < new Date().setHours(0,0,0,0) ? '#EF4444' : '#D4532F',
                  fontWeight: 500,
                }}>
                  {new Date(contact.follow_up_date + 'T00:00:00') < new Date().setHours(0,0,0,0)
                    ? 'Overdue'
                    : contact.follow_up_date === new Date().toISOString().split('T')[0]
                      ? 'Due today'
                      : `Due ${new Date(contact.follow_up_date + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`
                  }
                </span>
                {contact.follow_up_note && (
                  <span className="text-light"> — {contact.follow_up_note}</span>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right: Notes */}
        <div className="card">
          <h3 className="card-title mb-2">Notes</h3>
          <textarea
            className="form-textarea"
            value={notes}
            onChange={(e) => { setNotes(e.target.value); setNotesSaved(false); }}
            placeholder="Add notes about this contact..."
            style={{ minHeight: '200px' }}
          />
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.5rem' }}>
            <button className="btn btn-primary" onClick={handleSaveNotes} disabled={savingNotes}>
              {savingNotes ? 'Saving...' : 'Save Notes'}
            </button>
            {notesSaved && <span style={{ color: '#10B981', fontSize: '0.85rem' }}>Saved!</span>}
          </div>
        </div>
      </div>

      {/* Email History */}
      <div className="card mt-4">
        <h3 className="card-title mb-2">Email History ({emailHistory.length})</h3>

        {emailHistory.length === 0 ? (
          <div className="empty-state"><p>No emails sent to this contact yet.</p></div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Subject</th>
                  <th>Date</th>
                  <th>Source</th>
                  <th>Opened</th>
                  <th>Clicked</th>
                  <th>Replied</th>
                </tr>
              </thead>
              <tbody>
                {emailHistory.map((log) => (
                  <tr key={log.id}>
                    <td style={{ maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {log.subject}
                    </td>
                    <td style={{ fontSize: '0.8rem', color: '#6B7280', whiteSpace: 'nowrap' }}>
                      {formatDateTime(log.created_at)}
                    </td>
                    <td>
                      {log.campaign_id ? (
                        <Link to={`/campaigns/${log.campaign_id}`} style={{ color: '#3B82F6', textDecoration: 'none', fontSize: '0.85rem' }}>
                          {log.source}
                        </Link>
                      ) : (
                        <span style={{ fontSize: '0.85rem', color: '#6B7280' }}>{log.source}</span>
                      )}
                    </td>
                    <td>
                      {log.opened_at ? (
                        <span title={new Date(log.opened_at).toLocaleString()} style={{ color: '#3B82F6', fontWeight: 500 }}>
                          ✓ ({log.open_count})
                        </span>
                      ) : <span style={{ color: '#9CA3AF' }}>-</span>}
                    </td>
                    <td>
                      {log.clicked_at ? (
                        <span title={new Date(log.clicked_at).toLocaleString()} style={{ color: '#E8603C', fontWeight: 500 }}>
                          ✓ ({log.click_count})
                        </span>
                      ) : <span style={{ color: '#9CA3AF' }}>-</span>}
                    </td>
                    <td>
                      {log.replied_at ? (
                        <span title={new Date(log.replied_at).toLocaleString()} style={{ color: '#10B981', fontWeight: 500 }}>✓</span>
                      ) : <span style={{ color: '#9CA3AF' }}>-</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Cold Calls */}
      <div className="card mt-4">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
          <h3 className="card-title">Cold Calls ({coldCalls.length})</h3>
          <button
            className="btn btn-primary"
            onClick={() => { setEditingColdCall(null); setShowColdCallModal(true); }}
            style={{ padding: '0.35rem 0.75rem', fontSize: '0.85rem' }}
          >
            Log Cold Call
          </button>
        </div>

        {coldCalls.length === 0 ? (
          <div className="empty-state"><p>No cold calls logged yet.</p></div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Outcome</th>
                  <th>Duration</th>
                  <th>Notes</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {coldCalls.map((call) => (
                  <tr key={call.id}>
                    <td style={{ whiteSpace: 'nowrap', fontSize: '0.85rem' }}>
                      {formatDateTime(call.call_date)}
                    </td>
                    <td>
                      <span className="badge" style={{
                        background: call.outcome === 'connected' ? '#ECFDF5' :
                          call.outcome === 'not_interested' ? '#FEF2F2' :
                          call.outcome === 'callback_requested' ? '#FEF3C7' : '#F3F4F6',
                        color: call.outcome === 'connected' ? '#059669' :
                          call.outcome === 'not_interested' ? '#DC2626' :
                          call.outcome === 'callback_requested' ? '#D97706' : '#4B5563',
                      }}>
                        {call.outcome_label}
                      </span>
                    </td>
                    <td style={{ fontSize: '0.85rem', color: '#6B7280' }}>
                      {call.duration_minutes ? `${call.duration_minutes} min` : '-'}
                    </td>
                    <td style={{ maxWidth: '300px', fontSize: '0.85rem' }}>
                      {call.notes ? (
                        <span title={call.notes}>
                          {call.notes.length > 80 ? call.notes.substring(0, 80) + '...' : call.notes}
                        </span>
                      ) : (
                        <span style={{ color: '#9CA3AF' }}>-</span>
                      )}
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: '0.25rem' }}>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => { setEditingColdCall(call); setShowColdCallModal(true); }}
                          style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem' }}
                        >
                          Edit
                        </button>
                        <button
                          className="btn btn-sm"
                          onClick={async () => {
                            if (!confirm('Delete this cold call record?')) return;
                            try {
                              await deleteColdCall(call.id);
                              loadContact();
                            } catch {}
                          }}
                          style={{
                            padding: '0.2rem 0.5rem',
                            fontSize: '0.75rem',
                            background: 'none',
                            color: '#EF4444',
                            border: '1px solid #EF4444',
                          }}
                        >
                          Delete
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

      {showColdCallModal && (
        <ColdCallModal
          contactId={contact.id}
          editingCall={editingColdCall}
          onClose={() => { setShowColdCallModal(false); setEditingColdCall(null); }}
          onSaved={loadContact}
        />
      )}
    </div>
  );
}

export default ContactDetail;
