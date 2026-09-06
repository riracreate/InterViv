import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { fetchMe } from '../lib/api';
import ResourceLinks from '../components/ResourceLinks';
import AppNav from '../components/AppNav';

/** Skill-resources UI so /resources?skill_id= from coach/ATS resolves (not API-only). */
export default function Resources() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const skillId = params.get('skill_id') || '';
  const [authReady, setAuthReady] = useState(false);
  const [navUser, setNavUser] = useState({ userId: null, roleId: null });

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
          {skillId ? `Skill: ${skillId}` : 'Pass ?skill_id= to filter curated links.'}
        </p>
        <div className="mt-6">
          <ResourceLinks skillId={skillId || null} heading="Curated links" />
        </div>
      </div>
    </main>
  );
}
