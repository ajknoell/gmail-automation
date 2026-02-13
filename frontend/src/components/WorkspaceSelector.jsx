import { useState, useEffect, useRef } from 'react';
import { getWorkspaces, createWorkspace, updateWorkspace, setActiveWorkspaceId, getActiveWorkspaceId } from '../api/client';

const COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899', '#06B6D4', '#F97316'];

export default function WorkspaceSelector() {
  const [workspaces, setWorkspaces] = useState([]);
  const [active, setActive] = useState(null);
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [newColor, setNewColor] = useState(COLORS[0]);
  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName] = useState('');
  const dropdownRef = useRef(null);

  useEffect(() => {
    loadWorkspaces();
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setOpen(false);
        setCreating(false);
        setEditingId(null);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const loadWorkspaces = async () => {
    try {
      const res = await getWorkspaces();
      const list = res.data;
      setWorkspaces(list);

      // Set active workspace from localStorage or default
      const storedId = getActiveWorkspaceId();
      const found = list.find(ws => String(ws.id) === String(storedId));
      if (found) {
        setActive(found);
      } else if (list.length > 0) {
        const defaultWs = list.find(ws => ws.is_default) || list[0];
        setActive(defaultWs);
        setActiveWorkspaceId(String(defaultWs.id));
      }
    } catch (err) {
      console.error('Failed to load workspaces:', err);
    }
  };

  const handleSelect = (ws) => {
    setActive(ws);
    setActiveWorkspaceId(String(ws.id));
    setOpen(false);
  };

  const handleCreate = async () => {
    if (!newName.trim()) return;
    try {
      const res = await createWorkspace({ name: newName.trim(), color: newColor });
      const ws = res.data;
      setWorkspaces(prev => [...prev, ws]);
      setActive(ws);
      setActiveWorkspaceId(String(ws.id));
      setNewName('');
      setNewColor(COLORS[0]);
      setCreating(false);
      setOpen(false);
    } catch (err) {
      console.error('Failed to create workspace:', err);
    }
  };

  const startEditing = (e, ws) => {
    e.stopPropagation();
    setEditingId(ws.id);
    setEditName(ws.name);
  };

  const handleRename = async (wsId) => {
    if (!editName.trim()) { setEditingId(null); return; }
    try {
      const res = await updateWorkspace(wsId, { name: editName.trim() });
      const updated = res.data;
      setWorkspaces(prev => prev.map(w => w.id === wsId ? { ...w, name: updated.name } : w));
      if (active && active.id === wsId) {
        setActive(prev => ({ ...prev, name: updated.name }));
      }
      setEditingId(null);
    } catch (err) {
      console.error('Failed to rename workspace:', err);
    }
  };

  if (!active) return (
    <div style={{
      padding: '6px 12px',
      background: '#F3F4F6',
      borderRadius: '8px',
      fontSize: '14px',
      color: '#9CA3AF',
      flexShrink: 0,
    }}>
      Loading…
    </div>
  );

  return (
    <div ref={dropdownRef} style={{ position: 'relative', flexShrink: 0 }}>
      {/* Trigger button */}
      <button
        onClick={() => setOpen(!open)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '6px 12px',
          background: '#F3F4F6',
          border: '1px solid #E5E7EB',
          borderRadius: '8px',
          color: '#1F2937',
          cursor: 'pointer',
          fontSize: '14px',
          fontWeight: 500,
          transition: 'background 0.15s',
        }}
        onMouseEnter={(e) => e.currentTarget.style.background = '#E5E7EB'}
        onMouseLeave={(e) => e.currentTarget.style.background = '#F3F4F6'}
      >
        <span
          style={{
            width: '10px',
            height: '10px',
            borderRadius: '50%',
            background: active.color,
            flexShrink: 0,
          }}
        />
        <span>{active.name}</span>
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" style={{ opacity: 0.5 }}>
          <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </button>

      {/* Dropdown */}
      {open && (
        <div
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            marginTop: '4px',
            background: 'white',
            border: '1px solid #E5E7EB',
            borderRadius: '10px',
            boxShadow: '0 10px 25px rgba(0,0,0,0.15)',
            minWidth: '220px',
            zIndex: 1000,
            overflow: 'hidden',
          }}
        >
          {/* Workspace list */}
          <div style={{ padding: '4px 0' }}>
            {workspaces.map(ws => (
              <div key={ws.id}>
                {editingId === ws.id ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 14px' }}>
                    <span
                      style={{
                        width: '10px',
                        height: '10px',
                        borderRadius: '50%',
                        background: ws.color,
                        flexShrink: 0,
                      }}
                    />
                    <input
                      type="text"
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handleRename(ws.id);
                        if (e.key === 'Escape') setEditingId(null);
                      }}
                      onBlur={() => handleRename(ws.id)}
                      autoFocus
                      style={{
                        flex: 1,
                        padding: '4px 8px',
                        border: '1px solid #3B82F6',
                        borderRadius: '4px',
                        fontSize: '14px',
                        outline: 'none',
                        minWidth: 0,
                      }}
                    />
                  </div>
                ) : (
                  <button
                    onClick={() => handleSelect(ws)}
                    className="ws-item"
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '10px',
                      width: '100%',
                      padding: '10px 14px',
                      border: 'none',
                      background: ws.id === active.id ? '#F3F4F6' : 'transparent',
                      cursor: 'pointer',
                      fontSize: '14px',
                      color: '#1F2937',
                      textAlign: 'left',
                      transition: 'background 0.1s',
                    }}
                    onMouseEnter={(e) => {
                      if (ws.id !== active.id) e.currentTarget.style.background = '#F9FAFB';
                      e.currentTarget.querySelector('.ws-edit-btn').style.opacity = '1';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = ws.id === active.id ? '#F3F4F6' : 'transparent';
                      e.currentTarget.querySelector('.ws-edit-btn').style.opacity = '0';
                    }}
                  >
                    <span
                      style={{
                        width: '10px',
                        height: '10px',
                        borderRadius: '50%',
                        background: ws.color,
                        flexShrink: 0,
                      }}
                    />
                    <span style={{ flex: 1 }}>{ws.name}</span>
                    <span
                      className="ws-edit-btn"
                      onClick={(e) => startEditing(e, ws)}
                      title="Rename"
                      style={{
                        opacity: 0,
                        padding: '2px 4px',
                        borderRadius: '4px',
                        color: '#9CA3AF',
                        cursor: 'pointer',
                        transition: 'opacity 0.15s, color 0.15s',
                        lineHeight: 1,
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.color = '#4B5563'; }}
                      onMouseLeave={(e) => { e.currentTarget.style.color = '#9CA3AF'; }}
                    >
                      <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
                        <path d="M11.5 1.5L14.5 4.5M1 15L1.5 11.5L12 1L15 4L4.5 14.5L1 15Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    </span>
                    {ws.id === active.id && (
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                        <path d="M3 7L6 10L11 4" stroke="#3B82F6" strokeWidth="2" strokeLinecap="round" />
                      </svg>
                    )}
                  </button>
                )}
              </div>
            ))}
          </div>

          {/* Divider */}
          <div style={{ height: '1px', background: '#E5E7EB' }} />

          {/* Create new */}
          {creating ? (
            <div style={{ padding: '12px 14px' }}>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Workspace name..."
                autoFocus
                onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  border: '1px solid #D1D5DB',
                  borderRadius: '6px',
                  fontSize: '13px',
                  marginBottom: '8px',
                  boxSizing: 'border-box',
                  outline: 'none',
                }}
              />
              <div style={{ display: 'flex', gap: '6px', marginBottom: '10px', flexWrap: 'wrap' }}>
                {COLORS.map(c => (
                  <button
                    key={c}
                    onClick={() => setNewColor(c)}
                    style={{
                      width: '22px',
                      height: '22px',
                      borderRadius: '50%',
                      background: c,
                      border: newColor === c ? '2px solid #1F2937' : '2px solid transparent',
                      cursor: 'pointer',
                      padding: 0,
                    }}
                  />
                ))}
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  onClick={handleCreate}
                  style={{
                    flex: 1,
                    padding: '7px',
                    background: '#3B82F6',
                    color: 'white',
                    border: 'none',
                    borderRadius: '6px',
                    fontSize: '13px',
                    fontWeight: 500,
                    cursor: 'pointer',
                  }}
                >
                  Create
                </button>
                <button
                  onClick={() => { setCreating(false); setNewName(''); }}
                  style={{
                    padding: '7px 12px',
                    background: '#F3F4F6',
                    color: '#6B7280',
                    border: 'none',
                    borderRadius: '6px',
                    fontSize: '13px',
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <button
              onClick={() => setCreating(true)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                width: '100%',
                padding: '10px 14px',
                border: 'none',
                background: 'transparent',
                cursor: 'pointer',
                fontSize: '13px',
                color: '#6B7280',
                textAlign: 'left',
              }}
              onMouseEnter={(e) => e.currentTarget.style.background = '#F9FAFB'}
              onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M7 2V12M2 7H12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
              Create Workspace
            </button>
          )}
        </div>
      )}
    </div>
  );
}
