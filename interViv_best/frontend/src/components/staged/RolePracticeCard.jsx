import React, { useEffect, useState } from 'react';
import { fetchRoleCatalog, planRolePractice } from '../../lib/api';
import { filterRoles, swapCore } from '../../lib/rolePractice';

const SAMPLE_RESUME = {
  projects: ['churn study'],
  skills: { SQL: 'claimed_with_evidence', Statistics: 'missing' },
};

export default function RolePracticeCard() {
  const [roles, setRoles] = useState([]);
  const [query, setQuery] = useState('');
  const [roleId, setRoleId] = useState('data-analyst');
  const [level, setLevel] = useState('junior');
  const [length, setLength] = useState('quick');
  const [jd, setJd] = useState('');
  const [useSample, setUseSample] = useState(false);
  const [plan, setPlan] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchRoleCatalog().then(data => setRoles(data.roles || [])).catch(err => setError(err.message || 'Could not load roles.'));
  }, []);

  const visible = filterRoles(roles, query);
  const selected = roles.find(role => role.id === roleId);

  async function preview(event) {
    event?.preventDefault();
    setError('');
    try {
      const next = await planRolePractice({
        role_id: roleId,
        level,
        length,
        jd_skills: jd.split(',').map(item => item.trim()).filter(Boolean),
        resume: useSample && roleId === 'data-analyst' ? SAMPLE_RESUME : null,
      });
      setPlan(next);
    } catch (err) {
      setError(err.message || 'Could not build this plan.');
    }
  }

  function swap(index) {
    if (!plan) return;
    const next = swapCore(plan.slots, plan.alternatives, index);
    setPlan({ ...plan, ...next });
  }

  return <section className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5" data-testid="role-practice-card" aria-labelledby="role-practice-title">
    <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-ink-muted)]">Practice for a role</p>
    <h2 id="role-practice-title" className="mt-2 text-xl font-semibold">Practice for a role</h2>
    <p className="mt-2 text-sm text-[var(--color-ink-muted)]">Your job description and resume are used only to plan this practice. They are not part of your score.</p>
    <form className="mt-4 space-y-3" onSubmit={preview}>
      <label className="block text-sm">Search roles
        <input className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] p-2" value={query} onChange={event => setQuery(event.target.value)} data-testid="role-search" />
      </label>
      <label className="block text-sm">Role
        <select className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] p-2" value={roleId} onChange={event => setRoleId(event.target.value)} data-testid="role-select">
          {visible.map(role => <option key={role.id} value={role.id}>{role.title}</option>)}
        </select>
      </label>
      <div className="flex flex-wrap gap-3">
        <label className="text-sm">Level
          <select className="ml-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] p-2" value={level} onChange={event => setLevel(event.target.value)}>
            <option value="intern">Intern</option>
            <option value="junior">Junior</option>
            <option value="mid">Mid</option>
          </select>
        </label>
        <label className="text-sm">Length
          <select className="ml-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] p-2" value={length} onChange={event => setLength(event.target.value)} data-testid="role-length">
            <option value="quick">Quick · 15 min</option>
            <option value="full">Full · {selected?.practical_track && selected.practical_track !== 'none' ? '48' : '22'} min</option>
          </select>
        </label>
      </div>
      <label className="block text-sm">Job description skills, optional
        <textarea className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] p-2" rows={2} value={jd} onChange={event => setJd(event.target.value)} placeholder="SQL, statistics" />
      </label>
      {roleId === 'data-analyst' && <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={useSample} onChange={event => setUseSample(event.target.checked)} data-testid="sample-resume" />
        Use the sample resume
      </label>}
      <button type="submit" className="app-button app-button-primary">Preview plan</button>
    </form>
    {error && <p className="mt-3 text-sm text-[var(--color-danger)]" role="alert">{error}</p>}
    {plan && <div className="mt-4" data-testid="role-plan">
      <p className="text-sm font-semibold">{plan.title} · about {plan.estimated_minutes} minutes</p>
      <ol className="mt-2 space-y-2">
        {plan.slots.map((slot, index) => <li key={`${slot.kind}-${index}`} className="flex items-start justify-between gap-3 text-sm">
          <span>{slot.reason}{slot.practice_only ? ' · practice only' : ''}{slot.scored === false ? ' · not scored' : ''}</span>
          {slot.kind === 'core' && <button type="button" className="app-button" onClick={() => swap(index)}>Swap</button>}
        </li>)}
      </ol>
    </div>}
  </section>;
}
