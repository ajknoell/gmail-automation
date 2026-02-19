function BulkAddProgress() {
  return (
    <div style={{
      padding: '1.5rem',
      textAlign: 'center',
      borderRadius: '0.375rem',
      background: '#F9FAFB',
      border: '1px solid #E5E7EB',
    }}>
      <div style={{
        display: 'inline-block',
        marginBottom: '1rem',
      }}>
        <div style={{
          display: 'inline-block',
          width: '40px',
          height: '40px',
          borderRadius: '50%',
          border: '4px solid #E5E7EB',
          borderTop: '4px solid #3B82F6',
          animation: 'spin 1s linear infinite',
        }} />
      </div>

      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>

      <div style={{
        fontSize: '0.875rem',
        color: '#6B7280',
        marginBottom: '0.5rem',
      }}>
        Uploading contacts...
      </div>

      <div style={{
        fontSize: '0.75rem',
        color: '#9CA3AF',
      }}>
        This may take a moment depending on file size
      </div>
    </div>
  );
}

export default BulkAddProgress;
