import React, { useEffect, useState } from 'react';
import { ArrowDown, ArrowRight, ArrowUp, Plus, Trash2 } from 'lucide-react';
import { fetchMe } from '../lib/api';
import { readScoped, writeScoped } from '../lib/accountStorage';

const OPTIONS = ['Client', 'API gateway', 'Service', 'Database', 'Cache', 'Queue', 'Load balancer', 'Storage'];

/** An optional ordered sketch; only notes explicitly added to the answer are submitted. */
export default function ArchitectureSketch({ sessionId, round, onAddToNotes }) {
  const [userId, setUserId] = useState('');
  const [loaded, setLoaded] = useState(false);
  const [nodes, setNodes] = useState([]);
  const [kind, setKind] = useState(OPTIONS[0]);
  const [notice, setNotice] = useState('');
  const key = `architecture:${sessionId}:${round}`;

  useEffect(() => {
    let cancelled = false;
    fetchMe().then(me => {
      if (cancelled) return;
      const user = me.user || me;
      const id = user.id || user.user_id || '';
      const saved = readScoped('local', id, key);
      setUserId(id);
      setNodes(Array.isArray(saved) ? saved.filter(node => node?.id && typeof node.name === 'string') : []);
      setLoaded(true);
    }).catch(() => { if (!cancelled) { setNotice('Sketches cannot be saved on this device right now.'); setLoaded(true); } });
    return () => { cancelled = true; };
  }, [key]);

  useEffect(() => {
    if (!loaded || !userId) return;
    setNotice(writeScoped('local', userId, key, nodes) ? '' : 'Sketches cannot be saved on this device right now.');
  }, [key, loaded, nodes, userId]);

  function move(index, direction) {
    const other = index + direction;
    if (other < 0 || other >= nodes.length) return;
    const next = [...nodes];
    [next[index], next[other]] = [next[other], next[index]];
    setNodes(next);
  }

  return <section className="iv-architecture" aria-labelledby="architecture-heading">
    <div><p className="iv-page-kicker">Optional visual aid</p><h3 id="architecture-heading">Architecture sketch</h3>
      <p>Arrange components to outline a flow. Saved on this device; the diagram itself is not scored or included in your report.</p></div>
    <div className="iv-architecture-builder"><label><span className="sr-only">Component type</span><select value={kind} onChange={event => setKind(event.target.value)}>{OPTIONS.map(option => <option key={option}>{option}</option>)}</select></label>
      <button type="button" className="app-button" disabled={!loaded} onClick={() => setNodes(current => [...current, { id: `${Date.now()}-${Math.random()}`, name: kind }])}><Plus size={15} /> Add component</button>
      {nodes.length > 0 && <button type="button" className="app-button" onClick={() => onAddToNotes(`Architecture flow: ${nodes.map(node => node.name).join(' → ')}.`)}>Add flow to notes</button>}
    </div>
    {notice && <p role="status">{notice}</p>}
    {nodes.length ? <ol className="iv-architecture-nodes">{nodes.map((node, index) => <li key={node.id}>
      <span>{node.name}</span><div className="iv-architecture-actions">
        <button type="button" onClick={() => move(index, -1)} disabled={index === 0} aria-label={`Move ${node.name} earlier`}><ArrowUp size={14} /></button>
        <button type="button" onClick={() => move(index, 1)} disabled={index === nodes.length - 1} aria-label={`Move ${node.name} later`}><ArrowDown size={14} /></button>
        <button type="button" onClick={() => setNodes(current => current.filter(item => item.id !== node.id))} aria-label={`Remove ${node.name}`}><Trash2 size={14} /></button>
      </div>{index < nodes.length - 1 && <ArrowRight className="iv-architecture-arrow" size={16} aria-hidden="true" />}
    </li>)}</ol> : <p className="iv-architecture-empty">Add a component to start sketching.</p>}
  </section>;
}
