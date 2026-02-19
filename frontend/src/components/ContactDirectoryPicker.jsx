import { useState, useEffect } from 'react';
import { getContacts, getRecipients } from '../api/client';

function ContactDirectoryPicker({ selectedIds, onSelectionChange, campaignId }) {
  const [contacts, setContacts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [existingEmails, setExistingEmails] = useState(new Set());

  useEffect(() => {
    loadContacts();
    loadExistingRecipients();
  }, [campaignId]);

  const loadContacts = async () => {
    try {
      setLoading(true);
      const response = await getContacts({ limit: 1000 });
      setContacts(response.data || []);
      setError(null);
    } catch (err) {
      setError('Failed to load contacts');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const loadExistingRecipients = async () => {
    try {
      const response = await getRecipients(campaignId);
      const emails = new Set((response.data || []).map(r => r.email.toLowerCase()));
      setExistingEmails(emails);
    } catch (err) {
      console.error('Failed to load existing recipients:', err);
    }
  };

  const filteredContacts = contacts.filter(contact => {
    const matchesSearch = !searchTerm ||
      (contact.email && contact.email.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (contact.name && contact.name.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (contact.company && contact.company.toLowerCase().includes(searchTerm.toLowerCase()));

    // Don't show contacts already in campaign
    const isAlreadyAdded = existingEmails.has(contact.email.toLowerCase());

    return matchesSearch && !isAlreadyAdded;
  });

  const handleToggleContact = (contact) => {
    const newSelected = selectedIds.includes(contact.id)
      ? selectedIds.filter(id => id !== contact.id)
      : [...selectedIds, contact.id];

    const selectedContacts = contacts.filter(c => newSelected.includes(c.id));
    onSelectionChange(selectedContacts);
  };

  const handleSelectAll = () => {
    if (selectedIds.length === filteredContacts.length) {
      onSelectionChange([]);
    } else {
      onSelectionChange(filteredContacts);
    }
  };

  if (loading) {
    return <div style={{ padding: '2rem', textAlign: 'center', color: '#6B7280' }}>Loading contacts...</div>;
  }

  if (error) {
    return <div style={{ padding: '1rem', color: '#DC2626', background: '#FEF2F2', borderRadius: '0.375rem' }}>{error}</div>;
  }

  if (contacts.length === 0) {
    return <div style={{ padding: '2rem', textAlign: 'center', color: '#6B7280' }}>No contacts found</div>;
  }

  return (
    <div>
      {/* Search Input */}
      <div style={{ marginBottom: '1rem' }}>
        <input
          type="text"
          className="form-input"
          placeholder="Search by email, name, or company..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
      </div>

      {/* Select All Checkbox */}
      <div style={{ marginBottom: '1rem', paddingBottom: '1rem', borderBottom: '1px solid #E5E7EB' }}>
        <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={selectedIds.length > 0 && selectedIds.length === filteredContacts.length}
            onChange={handleSelectAll}
            style={{ marginRight: '0.5rem' }}
          />
          <span style={{ fontSize: '0.875rem', fontWeight: '500' }}>
            Select All ({filteredContacts.length})
          </span>
        </label>
      </div>

      {/* Contacts List */}
      <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
        {filteredContacts.length === 0 ? (
          <div style={{ padding: '1rem', textAlign: 'center', color: '#6B7280', fontSize: '0.875rem' }}>
            No contacts match your search
          </div>
        ) : (
          filteredContacts.map((contact) => (
            <div
              key={contact.id}
              style={{
                padding: '0.75rem',
                borderBottom: '1px solid #F3F4F6',
                display: 'flex',
                alignItems: 'flex-start',
                gap: '0.75rem',
              }}
            >
              <input
                type="checkbox"
                checked={selectedIds.includes(contact.id)}
                onChange={() => handleToggleContact(contact)}
                style={{ marginTop: '0.25rem', cursor: 'pointer' }}
              />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: '500', fontSize: '0.875rem', color: '#111827' }}>
                  {contact.name || 'Unknown'}
                </div>
                <div style={{ fontSize: '0.75rem', color: '#6B7280', marginTop: '0.125rem' }}>
                  {contact.email}
                </div>
                {contact.company && (
                  <div style={{ fontSize: '0.75rem', color: '#6B7280', marginTop: '0.125rem' }}>
                    {contact.company}
                  </div>
                )}
                {contact.status && (
                  <div style={{
                    fontSize: '0.625rem',
                    marginTop: '0.25rem',
                    padding: '0.125rem 0.375rem',
                    borderRadius: '0.25rem',
                    background: '#E0E7FF',
                    color: '#4338CA',
                    display: 'inline-block',
                  }}>
                    {contact.status}
                  </div>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default ContactDirectoryPicker;
