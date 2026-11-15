import React, { useState } from 'react';

const FIELDS = [
  ['situation', 'Situation', 'What was the context?'],
  ['task', 'Task', 'What were you responsible for?'],
  ['action', 'Action', 'What did you do?'],
  ['result', 'Result', 'What happened or what did you learn?'],
];

export default function StarComposer({ onInsert }) {
  const [parts, setParts] = useState({});
  const hasContent = FIELDS.some(([key]) => parts[key]?.trim());
  return <details className="iv-star-composer">
    <summary>Structure an answer with STAR</summary>
    <div className="iv-star-fields">
      <p>Draft a story, then add it to your answer to include it in your saved draft.</p>
      {FIELDS.map(([key, label, placeholder]) => <label key={key}>{label}
        <textarea value={parts[key] || ''} onChange={event => setParts(previous => ({ ...previous, [key]: event.target.value }))} placeholder={placeholder} rows={2} />
      </label>)}
      <button type="button" className="app-button" disabled={!hasContent} onClick={() => {
        const text = FIELDS.filter(([key]) => parts[key]?.trim()).map(([key, label]) => `${label}: ${parts[key].trim()}`).join('\n\n');
        onInsert(text);
        setParts({});
      }}>Add to answer</button>
    </div>
  </details>;
}
