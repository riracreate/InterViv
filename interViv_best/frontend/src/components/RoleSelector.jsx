import React, { useEffect, useRef, useState } from 'react';
import {
  fetchAvailability,
  fetchRoleCatalog,
  fetchTargetContext,
  planRolePractice,
  saveTargetContext,
  startSession,
} from '../lib/api';
import { swapCore } from '../lib/rolePractice';
import {
  ROLE_LEVELS,
  coreCompetencies,
  roleInterviewPayload,
  rolePlanRequest,
  roleTargetFromContext,
  roleTargetUpdate,
  slotLabel,
} from '../lib/roleTargets';

/**
 * Pick one of the starter roles and a level, optionally plan with your
 * resume skills, save it as your target, and start a role interview.
 * Replaces the company picker when ROLE_ONLY_TARGETS is on.
 */
export default function RoleSelector({
  isAuthenticated = true,
  candidateId = '',
  allowStart = true,
  onSaved,
  onStarted,
  heading = 'Target role',
}) {
  const [roles, setRoles] = useState([]);
  const [roleId, setRoleId] = useState('');
  const [level, setLevel] = useState('junior');
  const [length, setLength] = useState('quick');
  const [resumeRef, setResumeRef] = useState(candidateId || '');
  const [useResume, setUseResume] = useState(Boolean(candidateId));
  const [core, setCore] = useState(null);
  const [plan, setPlan] = useState(null);
  const [loadError, setLoadError] = useState('');
  const [planError, setPlanError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const picked = useRef(false);

  useEffect(() => {
    if (candidateId) {
      setResumeRef(candidateId);
      setUseResume(true);
    }
  }, [candidateId]);

  useEffect(() => {
    let cancelled = false;
    fetchRoleCatalog()
      .then(data => {
        if (cancelled) return;
        const list = data.roles || [];
        setRoles(list);
        if (!picked.current && list.length) setRoleId(current => current || list[0].id);
      })
      .catch(err => { if (!cancelled) setLoadError(err.message || 'Could not load roles.'); });
    if (isAuthenticated) {
      fetchTargetContext()
        .then(data => {
          if (cancelled) return;
          const saved = roleTargetFromContext(data);
          if (saved && !picked.current) {
            setRoleId(saved.role_id);
            setLevel(saved.level || 'junior');
          }
          const ref = data?.target?.resume_ref;
          if (ref && !candidateId) setResumeRef(ref);
        })
        .catch(() => {});
    }
    return () => { cancelled = true; };
  }, [isAuthenticated, candidateId]);

  useEffect(() => {
    if (!roleId || !allowStart) return undefined;
    let cancelled = false;
    setPlanError('');
    planRolePractice(rolePlanRequest({ roleId, level, length, candidateId: resumeRef, useResume, core }))
      .then(next => { if (!cancelled) setPlan(next); })
      .catch(err => {
        if (cancelled) return;
        setPlan(null);
        setPlanError(err.message || 'Could not plan this interview.');
      });
    return () => { cancelled = true; };
  }, [roleId, level, length, resumeRef, useResume, core, allowStart]);

  const choose = (setter) => (event) => {
    picked.current = true;
    setCore(null);
    setMessage('');
    setter(event.target.value);
  };

  const save = async () => {
    if (!roleId) return;
    setBusy(true);
    setMessage('');
    try {
      await saveTargetContext(roleTargetUpdate(roleId, level));
      setMessage('Saved as your target.');
      onSaved?.();
    } catch (err) {
      setMessage(err.message || 'Could not save your target.');
    } finally {
      setBusy(false);
    }
  };

  const swap = (index) => {
    if (!plan) return;
    const next = swapCore(plan.slots, plan.alternatives, index);
    setCore(coreCompetencies(next.slots));
  };

  const start = async () => {
    setBusy(true);
    setMessage('');
    try {
      const payload = roleInterviewPayload({
        roleId, level, length, candidateId: resumeRef, useResume, core: core || coreCompetencies(plan?.slots),
      });
      const availability = await fetchAvailability(payload);
      if (availability?.available === false) {
        const reasons = (availability.blocks || []).filter(b => b.available === false).map(b => b.reason).filter(Boolean);
        throw new Error(reasons.join(' ') || 'This interview cannot start right now.');
      }
      const started = await startSession(payload);
      onStarted?.(started);
    } catch (err) {
      setMessage(err.message || 'Could not start this interview.');
    } finally {
      setBusy(false);
    }
  };

  const selected = roles.find(role => role.id === roleId);
  const fullMinutes = selected?.practical_track && selected.practical_track !== 'none' ? 48 : 22;

  if (loadError) {
    return <div className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5 text-sm text-[var(--color-ink-muted)]" data-testid="role-selector" role="alert">
      {loadError} You can still practice by skill.
    </div>;
  }

  return <section className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5" data-testid="role-selector" aria-labelledby="role-selector-title">
    <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-ink-muted)]">Optional · skip for general practice</p>
    <h2 id="role-selector-title" className="mt-2 text-xl font-semibold text-[var(--color-ink)]">{heading}</h2>
    <p className="mt-2 text-sm text-[var(--color-ink-muted)]">Pick a role and level. Your resume only shapes which skills are asked; it is never part of your score.</p>
    <div className="mt-4 grid gap-3 sm:grid-cols-2">
      <label className="block text-sm text-[var(--color-ink)]">Role
        <select className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] p-2" value={roleId} onChange={choose(setRoleId)} data-testid="role-target-select">
          {roles.map(role => <option key={role.id} value={role.id}>{role.title}</option>)}
        </select>
      </label>
      <label className="block text-sm text-[var(--color-ink)]">Level
        <select className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] p-2" value={level} onChange={choose(setLevel)} data-testid="role-level-select">
          {ROLE_LEVELS.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}
        </select>
      </label>
    </div>
    {resumeRef && <label className="mt-3 flex items-center gap-2 text-sm text-[var(--color-ink)]">
      <input type="checkbox" checked={useResume} onChange={event => { setCore(null); setUseResume(event.target.checked); }} data-testid="role-use-resume" />
      Plan with my resume skills
    </label>}
    <div className="mt-4 flex flex-wrap items-center gap-2">
      {isAuthenticated && <button type="button" className="app-button" disabled={!roleId || busy} onClick={save} data-testid="role-target-save">Save as my target</button>}
    </div>
    {allowStart && <div className="mt-5 border-t border-[var(--color-border)] pt-4" data-testid="role-interview">
      <label className="text-sm text-[var(--color-ink)]">Length
        <select className="ml-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] p-2" value={length} onChange={choose(setLength)} data-testid="role-interview-length">
          <option value="quick">Quick · 15 min</option>
          <option value="full">Full · {fullMinutes} min</option>
        </select>
      </label>
      {planError && <p className="mt-3 text-sm text-[var(--color-danger)]" role="alert">{planError}</p>}
      {plan && <ol className="mt-3 space-y-2" data-testid="role-interview-plan">
        {plan.slots.map((slot, index) => {
          const label = slotLabel(slot);
          return <li key={`${slot.kind}-${index}`} className="flex items-start justify-between gap-3 text-sm">
            <span><span className="font-semibold">{label.stage}</span> · {label.text}{label.note ? <span className="text-[var(--color-ink-muted)]"> · {label.note}</span> : null}</span>
            {slot.kind === 'core' && plan.alternatives?.length > 0 && <button type="button" className="app-button" disabled={busy} onClick={() => swap(index)}>Swap</button>}
          </li>;
        })}
      </ol>}
      {plan && <p className="mt-3 text-xs text-[var(--color-ink-muted)]">About {plan.estimated_minutes} minutes. Answers are saved as you go; feedback appears when the interview ends.</p>}
      <button type="button" className="app-button app-button-primary mt-4" disabled={!roleId || !plan || busy} onClick={start} data-testid="role-interview-start">
        {busy ? 'Starting…' : 'Start role interview'}
      </button>
    </div>}
    {message && <p className="mt-3 text-sm text-[var(--color-ink-muted)]" role="status">{message}</p>}
  </section>;
}
