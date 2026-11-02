import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { fetchMe } from '../lib/api';
import ResourceLinks from '../components/ResourceLinks';
import AppNav from '../components/AppNav';

const CATEGORIES = ['DSA', 'System Design', 'Behavioral', 'SQL', 'OA / MCQ', 'Resume / ATS'];
const OTHER_SKILLS = ['DBMS', 'OOP', 'Operating Systems', 'Computer Networks', 'Python', 'Machine Learning'];

/** Skill-resources UI so /resources?skill_id= from coach/ATS resolves (not API-only). */
export default function Resources() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const skillId = params.get('skill_id') || 'DSA';
  const [skillInput, setSkillInput] = useState(skillId);
  const [authReady, setAuthReady] = useState(false);
  const [navUser, setNavUser] = useState({ userId: null, roleId: null });
  useEffect(() => { setSkillInput(skillId); }, [skillId]);

  useEffect(() => {
    let cancelled = false;
    const next = skillId
      ? `/resources?skill_id=${encodeURIComponent(skillId)}`
      : '/resources';
    fetchMe()
      .then((me) => {
        if (cancelled) return;
        setAuthReady(true);
        const u = me.user || me;
        setNavUser({
          userId: u.id || u.user_id || null,
          roleId: u.target_role_id || null,
        });
      })
      .catch(() => {
        if (!cancelled) navigate('/login', { state: { next } });
      });
    return () => {
      cancelled = true;
    };
  }, [navigate, skillId]);

  if (!authReady) {
    return (
      <main className="min-h-screen bg-[var(--color-surface)] grid place-items-center">
        <p className="text-sm text-[var(--color-ink-muted)]">Checking sign-in…</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[var(--color-surface)] text-[var(--color-ink)]">
      <div className="app-container">
        <AppNav userId={navUser.userId} roleId={navUser.roleId} />
        <h1 className="mt-6 text-[length:var(--text-3xl)] font-semibold" style={{ fontFamily: 'var(--font-display)' }}>
          Learning resources
        </h1>
        <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
          Courses, videos, practice sites, and guides for your next interview. Choose a category to get started.
        </p>
        <nav aria-label="Resource categories" className="mt-6 flex flex-wrap gap-2">
          {CATEGORIES.map(category => (
            <button key={category} type="button" aria-pressed={skillId === category}
              onClick={() => setParams({ skill_id: category })}
              className={`rounded-[var(--radius-pill)] border px-4 py-2 text-sm font-medium ${skillId === category ? 'border-[var(--color-ink)] bg-[var(--color-ink)] text-white' : 'border-[var(--color-border)] bg-white hover:bg-[var(--color-surface)]'}`}>
              {category}
            </button>
          ))}
        </nav>
        <form className="mt-6 flex flex-wrap items-end gap-3" onSubmit={event => { event.preventDefault(); setParams(skillInput.trim() ? { skill_id: skillInput.trim() } : {}); }}>
          <label className="flex-1 text-sm">Skill
            <input list="resource-skills" className="mt-2 block w-full rounded-[var(--radius-card)] border border-[var(--color-border)] bg-white px-3 py-2" value={skillInput} onChange={event => setSkillInput(event.target.value)} placeholder="For example, Python or DBMS" />
            <datalist id="resource-skills">{[...CATEGORIES, ...OTHER_SKILLS].map(skill => <option key={skill} value={skill} />)}</datalist>
          </label>
          <button type="submit" disabled={!skillInput.trim()} className="rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50">Find resources</button>
        </form>
        <div className="mt-6">
          <h2 className="text-lg font-semibold">{skillId}</h2>
          <p className="mt-1 text-xs text-[var(--color-ink-muted)]">Links open in a new tab. Some providers offer paid extras or require an account.</p>
          <ResourceLinks key={skillId} skillId={skillId} maxPerLevel={100} heading="Curated links" emptyMessage="No curated resources are available for this skill yet. Try another skill." />
        </div>
      </div>
    </main>
  );
}
