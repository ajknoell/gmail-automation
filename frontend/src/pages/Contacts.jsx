import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { getContacts, getTags, getContactStatuses, updateContact } from '../api/client';

function Contacts() {
  const [contacts, setContacts] = useState([]);
  const [search, setSearch] = useState('');
  const [sortField, setSortField] = useState('last_contacted_at');
  const [sortOrder, setSortOrder] = useState('desc');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [tags, setTags] = useState([]);
  const [statuses, setStatuses] = useState([]);
  const [activeTag, setActiveTag] = useState('');
  const [activeStatus, setActiveStatus] = useState('');
  const debounceRef = useRef(null);

  const loadContacts = async (params = {}) => {
    setLoading(true);
    try {
      const res = await getContacts({
        q: params.q !== undefined ? params.q : search,
        sort: params.sort || sortField,
        order: params.order || sortOrder,
        page: params.page || page,
        per_page: 50,
        tag: params.tag !== undefined ? params.tag : activeTag,
        status: params.status !== undefined ? params.status : activeStatus,
      });
      setContacts(res.data.contacts || []);
      setTotalPages(res.data.pages || 1);
      setTotal(res.data.total || 0);
    } catch {
      setContacts([]);
    }
    setLoading(false);
  };

  const loadAll = () => {
    loadContacts();
    getTags().then((res) => setTags(res.data || [])).catch(() => {});
    getContactStatuses().then((res) => setStatuses(res.data || [])).catch(() => {});
  };

  useEffect(() => {
    loadAll();
    const handleWsChange = () => loadAll();
    window.addEventListener('workspace-changed', handleWsChange);
    return () => window.removeEventListener('workspace-changed', handleWsChange);
  }, []);

  const handleSearchChange = (value) => {
    setSearch(value);
    setPage(1);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      loadContacts({ q: value, page: 1 });
    }, 300);
  };

  const handleSort = (field) => {
    const newOrder = sortField === field && sortOrder === 'desc' ? 'asc' : 'desc';
    setSortField(field);
    setSortOrder(newOrder);
    loadContacts({ sort: field, order: newOrder });
  };

  const handlePageChange = (newPage) => {
    setPage(newPage);
    loadContacts({ page: newPage });
  };

  const handleTagFilter = (tagName) => {
    const newTag = activeTag === tagName ? '' : tagName;
    setActiveTag(newTag);
    setPage(1);
    loadContacts({ tag: newTag, page: 1 });
  };

  const handleStatusFilter = (statusValue) => {
    const newStatus = activeStatus === statusValue ? '' : statusValue;
    setActiveStatus(newStatus);
    setPage(1);
    loadContacts({ status: newStatus, page: 1 });
  };

  const handleStatusChange = async (contactId, newStatus) => {
    try {
      await updateContact(contactId, { status: newStatus });
      // Update locally
      setContacts((prev) =>
        prev.map((c) => {
          if (c.id === contactId) {
            const s = statuses.find((st) => st.value === newStatus);
            return {
              ...c,
              status: newStatus,
              status_label: s?.label || newStatus,
              status_color: s?.color || '#6B7280',
            };
          }
          return c;
        })
      );
    } catch {
      // ignore
    }
  };

  const formatDate = (iso) => {
    if (!iso) return '-';
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now - d;
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays}d ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
    return d.toLocaleDateString();
  };

  const SortHeader = ({ field, children }) => (
    <th
      onClick={() => handleSort(field)}
      style={{ cursor: 'pointer', userSelect: 'none', whiteSpace: 'nowrap' }}
    >
      {children}
      {sortField === field && (
        <span style={{ marginLeft: '0.25rem', fontSize: '0.7rem' }}>
          {sortOrder === 'desc' ? '▼' : '▲'}
        </span>
      )}
    </th>
  );

  const StatusBadge = ({ status, color, label }) => (
    <span
      style={{
        display: 'inline-block',
        padding: '0.15rem 0.5rem',
        borderRadius: '9999px',
        fontSize: '0.7rem',
        fontWeight: 600,
        color: '#fff',
        backgroundColor: color,
        whiteSpace: 'nowrap',
      }}
    >
      {label}
    </span>
  );

  const TagChip = ({ name, color, active, onClick, count }) => (
    <button
      onClick={onClick}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.25rem',
        padding: '0.2rem 0.6rem',
        borderRadius: '9999px',
        fontSize: '0.75rem',
        fontWeight: 500,
        border: active ? `2px solid ${color}` : '1px solid #D1D5DB',
        background: active ? color + '20' : '#fff',
        color: active ? color : '#4B5563',
        cursor: 'pointer',
        transition: 'all 0.15s',
      }}
    >
      <span
        style={{
          width: '6px',
          height: '6px',
          borderRadius: '50%',
          backgroundColor: color,
          display: 'inline-block',
        }}
      />
      {name}
      {count !== undefined && (
        <span style={{ color: '#9CA3AF', fontSize: '0.65rem' }}>({count})</span>
      )}
    </button>
  );

  return (
    <div>
      <h1 className="mb-4">Contacts</h1>
      <p className="text-light mb-4">
        Directory of everyone you've emailed ({total} contact{total !== 1 ? 's' : ''})
      </p>

      {/* Search + Filters */}
      <div className="card mb-4">
        <input
          type="text"
          className="form-input"
          placeholder="Search by name, email, or company..."
          value={search}
          onChange={(e) => handleSearchChange(e.target.value)}
          style={{ marginBottom: '0.75rem' }}
        />

        {/* Status filters */}
        {statuses.length > 0 && (
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '0.75rem', color: '#9CA3AF', lineHeight: '1.8' }}>Status:</span>
            {statuses.map((s) => (
              <button
                key={s.value}
                onClick={() => handleStatusFilter(s.value)}
                style={{
                  padding: '0.2rem 0.6rem',
                  borderRadius: '9999px',
                  fontSize: '0.75rem',
                  fontWeight: 500,
                  border: activeStatus === s.value ? `2px solid ${s.color}` : '1px solid #D1D5DB',
                  background: activeStatus === s.value ? s.color + '20' : '#fff',
                  color: activeStatus === s.value ? s.color : '#4B5563',
                  cursor: 'pointer',
                }}
              >
                {s.label}
              </button>
            ))}
          </div>
        )}

        {/* Tag filters */}
        {tags.length > 0 && (
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.75rem', color: '#9CA3AF', lineHeight: '1.8' }}>Tags:</span>
            {tags.map((t) => (
              <TagChip
                key={t.id}
                name={t.name}
                color={t.color}
                count={t.contact_count}
                active={activeTag === t.name}
                onClick={() => handleTagFilter(t.name)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Contacts Table */}
      <div className="card">
        {loading ? (
          <div className="empty-state">
            <p>Loading contacts...</p>
          </div>
        ) : contacts.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">👤</div>
            <p>
              {search || activeTag || activeStatus
                ? 'No contacts match your filters'
                : 'No contacts yet. Send an email to start building your directory!'}
            </p>
          </div>
        ) : (
          <>
            <div style={{ overflowX: 'auto' }}>
              <table className="table">
                <thead>
                  <tr>
                    <SortHeader field="name">Name</SortHeader>
                    <SortHeader field="company">Company</SortHeader>
                    <SortHeader field="status">Status</SortHeader>
                    <th>Tags</th>
                    <th>Follow-Up</th>
                    <SortHeader field="last_contacted_at">Last Emailed</SortHeader>
                    <SortHeader field="total_emails_sent">Emails</SortHeader>
                    <th>Replied</th>
                  </tr>
                </thead>
                <tbody>
                  {contacts.map((c) => (
                    <tr key={c.id}>
                      <td>
                        <Link
                          to={`/contacts/${c.id}`}
                          style={{ color: '#3B82F6', textDecoration: 'none', fontWeight: 500 }}
                        >
                          {c.name || '—'}
                        </Link>
                        <div style={{ fontSize: '0.75rem', color: '#9CA3AF' }}>{c.email}</div>
                      </td>
                      <td>{c.company || '—'}</td>
                      <td>
                        <select
                          value={c.status || 'new'}
                          onChange={(e) => handleStatusChange(c.id, e.target.value)}
                          style={{
                            padding: '0.15rem 0.3rem',
                            borderRadius: '0.25rem',
                            border: '1px solid #D1D5DB',
                            fontSize: '0.75rem',
                            fontWeight: 500,
                            color: c.status_color,
                            background: '#fff',
                            cursor: 'pointer',
                          }}
                        >
                          {statuses.map((s) => (
                            <option key={s.value} value={s.value}>
                              {s.label}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: '0.25rem', flexWrap: 'wrap' }}>
                          {(c.tags || []).map((t) => (
                            <span
                              key={t.id}
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '0.15rem',
                                padding: '0.1rem 0.4rem',
                                borderRadius: '9999px',
                                fontSize: '0.65rem',
                                fontWeight: 500,
                                backgroundColor: t.color + '20',
                                color: t.color,
                                border: `1px solid ${t.color}40`,
                              }}
                            >
                              {t.name}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td style={{ fontSize: '0.8rem', whiteSpace: 'nowrap' }}>
                        {c.follow_up_date ? (() => {
                          const d = new Date(c.follow_up_date + 'T00:00:00');
                          const today = new Date();
                          today.setHours(0, 0, 0, 0);
                          const diff = Math.floor((d - today) / (1000 * 60 * 60 * 24));
                          const isOverdue = diff < 0;
                          const isToday = diff === 0;
                          return (
                            <span
                              style={{
                                color: isOverdue ? '#EF4444' : isToday ? '#F59E0B' : '#D4532F',
                                fontWeight: 500,
                              }}
                              title={c.follow_up_note || ''}
                            >
                              {isOverdue ? `${Math.abs(diff)}d overdue` : isToday ? 'Today' : diff === 1 ? 'Tomorrow' : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                            </span>
                          );
                        })() : <span style={{ color: '#D1D5DB' }}>-</span>}
                      </td>
                      <td style={{ fontSize: '0.8rem', color: '#6B7280', whiteSpace: 'nowrap' }}>
                        {formatDate(c.last_contacted_at)}
                      </td>
                      <td style={{ textAlign: 'center' }}>{c.total_emails_sent}</td>
                      <td>
                        {c.last_replied_at ? (
                          <span
                            title={new Date(c.last_replied_at).toLocaleString()}
                            style={{ color: '#10B981', fontWeight: 500 }}
                          >
                            ✓
                          </span>
                        ) : (
                          <span style={{ color: '#9CA3AF' }}>-</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {totalPages > 1 && (
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center',
                  gap: '0.5rem',
                  marginTop: '1rem',
                  paddingTop: '1rem',
                  borderTop: '1px solid #E5E7EB',
                }}
              >
                <button
                  className="btn btn-secondary"
                  onClick={() => handlePageChange(page - 1)}
                  disabled={page <= 1}
                  style={{ padding: '0.25rem 0.75rem', fontSize: '0.85rem' }}
                >
                  Previous
                </button>
                <span style={{ fontSize: '0.85rem', color: '#6B7280' }}>
                  Page {page} of {totalPages}
                </span>
                <button
                  className="btn btn-secondary"
                  onClick={() => handlePageChange(page + 1)}
                  disabled={page >= totalPages}
                  style={{ padding: '0.25rem 0.75rem', fontSize: '0.85rem' }}
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default Contacts;
