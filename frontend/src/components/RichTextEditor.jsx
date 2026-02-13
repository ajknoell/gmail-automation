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
 * Props:
 *   value: HTML string
 *   onChange: (html) => void
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
  const modules = {
    toolbar: compact
      ? [['bold', 'italic', 'underline'], ['link'], [{ list: 'ordered' }, { list: 'bullet' }], ['clean']]
      : TOOLBAR_OPTIONS,
  };

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
        value={value}
        onChange={onChange}
        modules={modules}
        placeholder={placeholder}
      />
    </div>
  );
}
