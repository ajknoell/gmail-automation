import { useRef } from 'react';
import { uploadAttachments, deleteAttachment } from '../api/client';

/**
 * Reusable attachment picker component.
 *
 * Props:
 *   attachments: array of {id, filename, original_name, size, content_type}
 *   onChange: (newAttachments) => void
 *   compact: boolean — if true, renders inline (for reply panel)
 */

const formatSize = (bytes) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

export default function AttachmentPicker({ attachments = [], onChange, compact = false }) {
  const fileRef = useRef(null);

  const handleFiles = async (e) => {
    const files = Array.from(e.target.files);
    if (!files.length) return;

    try {
      const res = await uploadAttachments(files);
      const uploaded = res.data || [];
      onChange([...attachments, ...uploaded]);
    } catch (err) {
      console.error('Upload failed:', err);
      alert('Failed to upload file(s)');
    }

    // Reset input so same file can be re-selected
    if (fileRef.current) fileRef.current.value = '';
  };

  const handleRemove = async (att) => {
    try {
      await deleteAttachment(att.id);
    } catch {
      // File may already be gone — proceed with UI removal
    }
    onChange(attachments.filter((a) => a.id !== att.id));
  };

  return (
    <div>
      <input
        ref={fileRef}
        type="file"
        multiple
        onChange={handleFiles}
        style={{ display: 'none' }}
      />

      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
        <button
          type="button"
          className={compact ? 'btn btn-secondary btn-sm' : 'btn btn-secondary'}
          onClick={() => fileRef.current?.click()}
          style={compact ? { padding: '4px 10px', fontSize: '13px' } : undefined}
        >
          {compact ? '📎 Attach' : '📎 Attach Files'}
        </button>

        {attachments.map((att) => (
          <div
            key={att.id}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 10px',
              backgroundColor: '#EEF2FF',
              borderRadius: '6px',
              fontSize: '13px',
              color: '#4338CA',
              border: '1px solid #E0E7FF',
            }}
          >
            <a
              href={`http://localhost:5001/api/attachments/${att.id}`}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                maxWidth: '180px',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                color: '#4338CA',
                textDecoration: 'none',
                cursor: 'pointer',
              }}
              title={`Preview ${att.original_name}`}
              onMouseOver={(e) => e.target.style.textDecoration = 'underline'}
              onMouseOut={(e) => e.target.style.textDecoration = 'none'}
            >
              {att.original_name}
            </a>
            <span style={{ color: '#9CA3AF', fontSize: '11px' }}>{formatSize(att.size)}</span>
            <button
              type="button"
              onClick={() => handleRemove(att)}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: '#9CA3AF',
                fontSize: '16px',
                lineHeight: 1,
                padding: '0 2px',
              }}
              title="Remove"
            >
              &times;
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
