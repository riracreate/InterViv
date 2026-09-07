import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { fetchMe } from '../lib/api';
import ResourceLinks from '../components/ResourceLinks';
import AppNav from '../components/AppNav';

/** Skill-resources UI so /resources?skill_id= from coach/ATS resolves (not API-only). */
export default function Resources() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const skillId = params.get('skill_id') || '';
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
      <div className="mx-auto w-full max-w-3xl px-[var(--space-4)] py-[var(--space-6)]">
        <AppNav userId={navUser.userId} roleId={navUser.roleId} />
        <h1 className="mt-6 text-[length:var(--text-3xl)] font-semibold" style={{ fontFamily: 'var(--font-display)' }}>
          Learning resources
        </h1>
        <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
          {skillId ? `Skill: ${skillId}` : 'Explore curated learning links for the skills you want to practice.'}
        </p>
        <form className="mt-6 flex flex-wrap items-end gap-3" onSubmit={event => { event.preventDefault(); setParams(skillInput.trim() ? { skill_id: skillInput.trim() } : {}); }}>
          <label className="flex-1 text-sm">Skill
            <input className="mt-2 block w-full rounded-[var(--radius-card)] border border-[var(--color-border)] bg-white px-3 py-2" value={skillInput} onChange={event => setSkillInput(event.target.value)} placeholder="For example, Python or DBMS" />
          </label>
          <button type="submit" disabled={!skillInput.trim()} className="rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50">Find resources</button>
        </form>
        <div className="mt-6">
          {skillId ? <ResourceLinks skillId={skillId} heading="Curated links" emptyMessage="No curated resources are available for this skill yet. Try another skill." /> : <p className="text-sm text-[var(--color-ink-muted)]">Enter a skill to explore its available learning links. External resources open only when you choose a link.</p>}
        </div>
      </div>
    </main>
  );
}
