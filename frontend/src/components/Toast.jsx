import { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react';

const ToastContext = createContext();

const noop = () => {};

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    console.warn('useToast must be used within ToastProvider');
    return noop;
  }
  return ctx;
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const timeoutsRef = useRef(new Map());

  // Cleanup all timeouts on unmount
  useEffect(() => {
    const timeouts = timeoutsRef.current;
    return () => {
      timeouts.forEach(tid => clearTimeout(tid));
      timeouts.clear();
    };
  }, []);

  const showToast = useCallback((message, type = 'info') => {
    const validTypes = ['success', 'error', 'info'];
    const safeType = validTypes.includes(type) ? type : 'info';
    const id = Date.now() + Math.random();
    setToasts(prev => [...prev, { id, message, type: safeType }]);
    const tid = setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
      timeoutsRef.current.delete(id);
    }, 4000);
    timeoutsRef.current.set(id, tid);
  }, []);

  const dismiss = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
    const tid = timeoutsRef.current.get(id);
    if (tid) { clearTimeout(tid); timeoutsRef.current.delete(id); }
  }, []);

  return (
    <ToastContext.Provider value={showToast}>
      {children}
      {toasts.length > 0 && (
        <div className="toast-container">
          {toasts.map(t => (
            <div key={t.id} className={`toast toast-${t.type}`}>
              <span>{t.message}</span>
              <button className="toast-close" onClick={() => dismiss(t.id)} aria-label="Close notification">&times;</button>
            </div>
          ))}
        </div>
      )}
    </ToastContext.Provider>
  );
}
