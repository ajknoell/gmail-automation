import { useState, useRef } from 'react';
import {
  addRecipientToCampaign,
  addRecipientsBulkToCampaign,
  getContacts,
  checkAddRecipientStatus,
} from '../api/client';
import ContactDirectoryPicker from './ContactDirectoryPicker';
import BulkAddProgress from './BulkAddProgress';

function AddContactToRunningCampaignModal({ campaignId, onClose, onSuccess }) {
  const [activeTab, setActiveTab] = useState('directory');
  const [selectedContacts, setSelectedContacts] = useState([]);
  const [manualData, setManualData] = useState({ email: '', name: '', company: '', custom_fields: {} });
  const [csvFile, setCsvFile] = useState(null);
  const [csvMapping, setCsvMapping] = useState(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [bulkProgress, setBulkProgress] = useState(null);

  const mouseDownTarget = useRef(null);

  const validateEmail = (email) => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  };

  const handleAddDirectory = async () => {
    if (selectedContacts.length === 0) {
      setError('Please select at least one contact');
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      let addedCount = 0;
      let duplicateCount = 0;

      for (const contact of selectedContacts) {
        try {
          await addRecipientToCampaign(campaignId, {
            source: 'directory',
            contact_id: contact.id,
          });
          addedCount++;
        } catch (err) {
          if (err.response?.data?.duplicate) {
            duplicateCount++;
          } else {
            throw err;
          }
        }
      }

      setSuccess(`Added ${addedCount} contact${addedCount !== 1 ? 's' : ''}${duplicateCount > 0 ? `, ${duplicateCount} duplicate${duplicateCount !== 1 ? 's' : ''}` : ''}`);
      setSelectedContacts([]);

      if (onSuccess) {
        onSuccess();
      }

      // Close modal after brief delay
      setTimeout(() => {
        onClose();
      }, 1500);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to add contacts');
    } finally {
      setLoading(false);
    }
  };

  const handleAddManual = async (e) => {
    e.preventDefault();

    if (!validateEmail(manualData.email)) {
      setError('Please enter a valid email address');
      return;
    }

    if (!manualData.name || manualData.name.trim() === '') {
      setError('Please enter a name');
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      await addRecipientToCampaign(campaignId, {
        source: 'manual',
        email: manualData.email,
        name: manualData.name,
        company: manualData.company,
        custom_fields: manualData.custom_fields,
      });

      setSuccess('Contact added successfully!');
      setManualData({ email: '', name: '', company: '', custom_fields: {} });

      if (onSuccess) {
        onSuccess();
      }

      // Close modal after brief delay
      setTimeout(() => {
        onClose();
      }, 1500);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to add contact');
    } finally {
      setLoading(false);
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setCsvFile(file);
      setError(null);
    }
  };

  const handleBulkUpload = async () => {
    if (!csvFile) {
      setError('Please select a CSV file');
      return;
    }

    setLoading(true);
    setError(null);
    setBulkProgress({ status: 'uploading', added: 0, skipped: 0, duplicates: 0 });

    try {
      const result = await addRecipientsBulkToCampaign(campaignId, csvFile, csvMapping);

      setBulkProgress({
        status: 'complete',
        added: result.data.added,
        skipped: result.data.skipped,
        duplicates: result.data.duplicates,
        total: result.data.total_processed,
      });

      setSuccess(result.data.message);
      setCsvFile(null);

      if (onSuccess) {
        onSuccess();
      }

      // Close modal after delay
      setTimeout(() => {
        onClose();
      }, 2000);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to upload CSV');
      setBulkProgress(null);
    } finally {
      setLoading(false);
    }
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
      <div className="modal" style={{ maxWidth: '600px', maxHeight: '90vh', overflowY: 'auto' }}>
        <div className="modal-header">
          <h3 className="modal-title">Add Contacts to Campaign</h3>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>

        {/* Tabs */}
        <div style={{ borderBottom: '1px solid #E5E7EB', display: 'flex' }}>
          {['directory', 'manual', 'csv'].map((tab) => (
            <button
              key={tab}
              onClick={() => {
                setActiveTab(tab);
                setError(null);
                setSuccess(null);
              }}
              style={{
                padding: '0.75rem 1.5rem',
                borderBottom: activeTab === tab ? '2px solid #3B82F6' : 'none',
                color: activeTab === tab ? '#3B82F6' : '#6B7280',
                backgroundColor: 'transparent',
                border: 'none',
                cursor: 'pointer',
                fontWeight: activeTab === tab ? '500' : 'normal',
              }}
            >
              {tab === 'directory' && 'Directory'}
              {tab === 'manual' && 'Manual'}
              {tab === 'csv' && 'Bulk Import'}
            </button>
          ))}
        </div>

        <div className="modal-body">
          {/* Error/Success Messages */}
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

          {success && (
            <div style={{
              padding: '0.75rem',
              marginBottom: '1rem',
              borderRadius: '0.375rem',
              background: '#F0FDF4',
              color: '#16A34A',
              fontSize: '0.875rem',
            }}>
              ✓ {success}
            </div>
          )}

          {/* Directory Tab */}
          {activeTab === 'directory' && (
            <div>
              <p style={{ marginBottom: '1rem', color: '#6B7280', fontSize: '0.875rem' }}>
                Select contacts from your directory to add to this campaign
              </p>
              <ContactDirectoryPicker
                selectedIds={selectedContacts.map(c => c.id)}
                onSelectionChange={(contacts) => setSelectedContacts(contacts)}
                campaignId={campaignId}
              />
            </div>
          )}

          {/* Manual Tab */}
          {activeTab === 'manual' && (
            <form onSubmit={handleAddManual}>
              <div className="form-group">
                <label className="form-label">Email *</label>
                <input
                  type="email"
                  className="form-input"
                  value={manualData.email}
                  onChange={(e) => setManualData({ ...manualData, email: e.target.value })}
                  placeholder="john@example.com"
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Name *</label>
                <input
                  type="text"
                  className="form-input"
                  value={manualData.name}
                  onChange={(e) => setManualData({ ...manualData, name: e.target.value })}
                  placeholder="John Doe"
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Company</label>
                <input
                  type="text"
                  className="form-input"
                  value={manualData.company}
                  onChange={(e) => setManualData({ ...manualData, company: e.target.value })}
                  placeholder="Acme Corp"
                />
              </div>

              <div style={{ marginTop: '1.5rem' }}>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={loading || !manualData.email || !manualData.name}
                  style={{ width: '100%' }}
                >
                  {loading ? 'Adding...' : 'Add Contact'}
                </button>
              </div>
            </form>
          )}

          {/* CSV Tab */}
          {activeTab === 'csv' && (
            <div>
              <p style={{ marginBottom: '1rem', color: '#6B7280', fontSize: '0.875rem' }}>
                Upload a CSV file with email, name, and company columns
              </p>

              {bulkProgress && bulkProgress.status === 'uploading' && (
                <BulkAddProgress />
              )}

              {bulkProgress && bulkProgress.status === 'complete' && (
                <div style={{
                  padding: '1rem',
                  borderRadius: '0.375rem',
                  background: '#F0FDF4',
                  color: '#16A34A',
                  fontSize: '0.875rem',
                }}>
                  <div style={{ fontWeight: '500', marginBottom: '0.5rem' }}>Upload Complete</div>
                  <div>Added: {bulkProgress.added}</div>
                  {bulkProgress.skipped > 0 && <div>Skipped: {bulkProgress.skipped}</div>}
                  {bulkProgress.duplicates > 0 && <div>Duplicates: {bulkProgress.duplicates}</div>}
                </div>
              )}

              {!bulkProgress && (
                <>
                  <div style={{
                    border: '2px dashed #D1D5DB',
                    borderRadius: '0.5rem',
                    padding: '2rem',
                    textAlign: 'center',
                    marginBottom: '1rem',
                  }}>
                    <input
                      type="file"
                      accept=".csv,.xlsx"
                      onChange={handleFileChange}
                      style={{
                        display: 'none',
                      }}
                      id="csv-upload"
                    />
                    <label htmlFor="csv-upload" style={{ cursor: 'pointer', display: 'block' }}>
                      <div style={{ color: '#3B82F6', fontWeight: '500', marginBottom: '0.5rem' }}>
                        {csvFile ? csvFile.name : 'Click to upload or drag and drop'}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: '#6B7280' }}>
                        CSV or Excel files
                      </div>
                    </label>
                  </div>

                  <button
                    onClick={handleBulkUpload}
                    className="btn btn-primary"
                    disabled={!csvFile || loading}
                    style={{ width: '100%' }}
                  >
                    {loading ? 'Uploading...' : 'Upload CSV'}
                  </button>
                </>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="modal-footer">
          {activeTab === 'directory' && (
            <>
              <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
              <button
                className="btn btn-primary"
                onClick={handleAddDirectory}
                disabled={loading || selectedContacts.length === 0}
              >
                {loading ? 'Adding...' : `Add ${selectedContacts.length} Contact${selectedContacts.length !== 1 ? 's' : ''}`}
              </button>
            </>
          )}
          {activeTab === 'manual' && !success && (
            <button className="btn btn-secondary" onClick={onClose}>Close</button>
          )}
          {activeTab === 'csv' && !bulkProgress && (
            <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
          )}
        </div>
      </div>
    </div>
  );
}

export default AddContactToRunningCampaignModal;
