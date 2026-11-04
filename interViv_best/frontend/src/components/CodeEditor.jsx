import React, { useEffect, useRef, useState } from 'react';

export default function CodeEditor({ value, language, documentKey, onChange, onRun, onSubmit, readOnly }) {
  const container = useRef(null);
  const editor = useRef(null);
  const models = useRef(new Map());
  const api = useRef(null);
  const callbacks = useRef({ onChange, onRun, onSubmit });
  callbacks.current = { onChange, onRun, onSubmit };
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    let cancelled = false;
    let subscription;
    import('../lib/codingEditor').then(({ monaco }) => {
      if (cancelled) return;
      api.current = monaco;
      const model = monaco.editor.createModel(value, language);
      models.current.set(documentKey, model);
      editor.current = monaco.editor.create(container.current, {
        model, theme: 'interviv-code', automaticLayout: true, fontSize: 14, lineHeight: 23,
        tabSize: 4, insertSpaces: true, minimap: { enabled: false }, scrollBeyondLastLine: false,
        padding: { top: 18 }, lineNumbers: 'on', bracketPairColorization: { enabled: true },
        readOnly, accessibilitySupport: 'auto', ariaLabel: `${language} solution editor`,
      });
      subscription = editor.current.onDidChangeModelContent(() => callbacks.current.onChange(editor.current.getValue()));
      editor.current.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => callbacks.current.onRun());
      editor.current.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyMod.Shift | monaco.KeyCode.Enter, () => callbacks.current.onSubmit());
      setLoaded(true);
    }).catch(() => { if (!cancelled) setError('Editor loading failed. Your solution is available in the text editor.'); });
    return () => { cancelled = true; subscription?.dispose(); editor.current?.dispose(); models.current.forEach(m => m.dispose()); };
  }, []);
  useEffect(() => {
    if (!editor.current) return;
    if (!models.current.has(documentKey)) models.current.set(documentKey, api.current.editor.createModel(value, language));
    const model = models.current.get(documentKey);
    if (editor.current.getModel() !== model) editor.current.setModel(model);
    if (model.getValue() !== value) model.setValue(value);
    editor.current.updateOptions({ readOnly, ariaLabel: `${language} solution editor` });
  }, [value, language, documentKey, readOnly, loaded]);
  return <div className="coding-editor-shell">
    <div ref={container} className="coding-monaco" style={{ display: loaded ? 'block' : 'none' }} />
    {!loaded && <>{error && <p role="alert" className="coding-editor-notice">{error}</p>}
      <textarea aria-label={`${language} solution editor`} spellCheck={false} value={value} readOnly={readOnly}
        onChange={event => onChange(event.target.value)} className="coding-fallback" /></>}
  </div>;
}
