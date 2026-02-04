import { useState, useEffect } from 'react';
import { getTemplates, createTemplate, updateTemplate, deleteTemplate } from '../api/client';

function Templates() {
  const [templates, setTemplates] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ name: '', subject: '', body: '' });

  useEffect(() => {
    loadTemplates();
  }, []);

  const loadTemplates = () => {
    getTemplates().then((res) => setTemplates(res.data));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editing) {
        await updateTemplate(editing.id, form);
      } else {
        await createTemplate(form);
      }
      setShowModal(false);
      setEditing(null);
      setForm({ name: '', subject: '', body: '' });
      loadTemplates();
    } catch (error) {
      alert('Failed to save template');
    }
  };

  const handleEdit = (template) => {
    setEditing(template);
    setForm({ name: template.name, subject: template.subject, body: template.body });
    setShowModal(true);
  };

  const handleDelete = async (id) => {
    if (!confirm('Are you sure you want to delete this template?')) return;
    try {
      await deleteTemplate(id);
      loadTemplates();
    } catch (error) {
      alert('Failed to delete template');
    }
  };

  const openNewModal = () => {
    setEditing(null);
    setForm({ name: '', subject: '', body: '' });
    setShowModal(true);
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h1>Email Templates</h1>
        <button className="btn btn-primary" onClick={openNewModal}>
          + New Template
        </button>
      </div>

      {templates.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="empty-state-icon">📝</div>
            <p>No templates yet. Create your first template!</p>
            <button className="btn btn-primary mt-2" onClick={openNewModal}>
              Create Template
            </button>
          </div>
        </div>
      ) : (
        <div className="grid grid-2">
          {templates.map((template) => (
            <div key={template.id} className="card">
              <div className="card-header">
                <h3 className="card-title">{template.name}</h3>
                <div className="flex gap-1">
                  <button className="btn btn-secondary btn-sm" onClick={() => handleEdit(template)}>
                    Edit
                  </button>
                  <button className="btn btn-danger btn-sm" onClick={() => handleDelete(template.id)}>
                    Delete
                  </button>
                </div>
              </div>
              <p className="text-sm mb-2"><strong>Subject:</strong> {template.subject}</p>
              <p className="text-sm text-light" style={{ whiteSpace: 'pre-wrap', maxHeight: '100px', overflow: 'hidden' }}>
                {template.body.substring(0, 200)}...
              </p>
              {template.variables && template.variables.length > 0 && (
                <div className="mt-2">
                  <span className="text-sm text-light">Variables: </span>
                  {template.variables.map((v) => (
                    <span key={v} className="badge badge-draft" style={{ marginRight: '0.25rem' }}>
                      {`{{${v}}}`}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '600px' }}>
            <div className="modal-header">
              <h3 className="modal-title">{editing ? 'Edit Template' : 'New Template'}</h3>
              <button className="modal-close" onClick={() => setShowModal(false)}>×</button>
            </div>
            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Template Name</label>
                  <input
                    type="text"
                    className="form-input"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    placeholder="e.g., Cold Outreach"
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Email Subject</label>
                  <input
                    type="text"
                    className="form-input"
                    value={form.subject}
                    onChange={(e) => setForm({ ...form, subject: e.target.value })}
                    placeholder="e.g., Quick question about {{company}}"
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Email Body</label>
                  <textarea
                    className="form-textarea"
                    value={form.body}
                    onChange={(e) => setForm({ ...form, body: e.target.value })}
                    placeholder="Hi {{name}},&#10;&#10;I noticed that {{company}} is doing great work in..."
                    required
                    style={{ minHeight: '200px' }}
                  />
                </div>
                <p className="text-sm text-light">
                  Use {'{{variable}}'} syntax for personalization. Common variables: name, company, email
                </p>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  {editing ? 'Update' : 'Create'} Template
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default Templates;
