import { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import ReactQuill from 'react-quill-new';
import 'react-quill-new/dist/quill.snow.css';

const TOOLBAR_OPTIONS = [
  [{ header: [1, 2, 3, false] }],
  [{ size: ['small', false, 'large', 'huge'] }],
  ['bold', 'italic', 'underline', 'strike'],
  [{ color: [] }, { background: [] }],
  ['link'],
  [{ list: 'ordered' }, { list: 'bullet' }],
  [{ align: [] }],
  ['clean'],
];

/**
 * Reusable rich text editor component.
 *
 * Uses internal state to avoid re-render lag. Saves are debounced (800ms)
 * and also fire on blur so edits are never lost.
 *
 * Props:
 *   value: HTML string (used as initial value; external changes only apply
 *          when the value is replaced wholesale, e.g. after regeneration)
 *   onChange: (html) => void — called on debounced save and blur
 *   placeholder: string
 *   style: object — applied to the wrapper div
 *   minHeight: string — min height for the editor area (default '200px')
 *   compact: boolean — smaller toolbar for inline use
 */
export default function RichTextEditor({
  value = '',
  onChange,
  placeholder = '',
  style = {},
  minHeight = '200px',
  compact = false,
}) {
  const [localValue, setLocalValue] = useState(value);
  const debounceRef = useRef(null);
  const lastSavedRef = useRef(value);

  // Sync from parent when the value is replaced externally (e.g. regeneration).
  // We compare against lastSavedRef to avoid overwriting the user's in-progress edits.
  useEffect(() => {
    if (value !== lastSavedRef.current) {
      setLocalValue(value);
      lastSavedRef.current = value;
    }
  }, [value]);

  const handleChange = useCallback((html) => {
    setLocalValue(html);
    // Debounce the save
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      if (onChange && html !== lastSavedRef.current) {
        lastSavedRef.current = html;
        onChange(html);
      }
    }, 800);
  }, [onChange]);

  const handleBlur = useCallback(() => {
    // Flush any pending debounce and save immediately
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (onChange && localValue !== lastSavedRef.current) {
      lastSavedRef.current = localValue;
      onChange(localValue);
    }
  }, [onChange, localValue]);

  // Clean up timeout on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const modules = useMemo(() => ({
    toolbar: compact
      ? [['bold', 'italic', 'underline'], ['link'], [{ list: 'ordered' }, { list: 'bullet' }], ['clean']]
      : TOOLBAR_OPTIONS,
  }), [compact]);

  return (
    <div
      className="rich-text-editor"
      style={style}
    >
      <style>{`
        .rich-text-editor .ql-container {
          min-height: ${minHeight};
          font-size: 14px;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }
        .rich-text-editor .ql-editor {
          min-height: ${minHeight};
        }
        .rich-text-editor .ql-toolbar {
          border-radius: 8px 8px 0 0;
          border-color: #D1D5DB;
          background: #F9FAFB;
        }
        .rich-text-editor .ql-container {
          border-radius: 0 0 8px 8px;
          border-color: #D1D5DB;
        }
        .rich-text-editor .ql-editor.ql-blank::before {
          color: #9CA3AF;
          font-style: normal;
        }
      `}</style>
      <ReactQuill
        theme="snow"
        value={localValue}
        onChange={handleChange}
        onBlur={handleBlur}
        modules={modules}
        placeholder={placeholder}
      />
    </div>
  );
}
