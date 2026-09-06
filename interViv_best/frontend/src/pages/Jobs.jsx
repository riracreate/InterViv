import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { fetchMe, fetchJobs, fetchJobPractice, saveInterviewState } from '../lib/api';
import { mapJobCard, jobApplyHref } from '../lib/jobsMapping';
import AppNav from '../components/AppNav';

export default function Jobs() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [authReady, setAuthReady] = useState(false);
  const [navUser, setNavUser] = useState({ userId: null, roleId: null });
  const [q, setQ] = useState(searchParams.get('q') || 'software intern OR backend OR data');
  const [where, setWhere] = useState(searchParams.get('where') || 'Pune');
  const [jobs, setJobs] = useState([]);
  const [meta, setMeta] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const returnTo = `/jobs${window.location.search || ''}`;
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
        if (!cancelled) navigate('/login', { state: { next: returnTo } });
      });
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  const load = async (nextQ = q, nextWhere = where) => {
    setBusy(true);
    setError('');
    try {
      const data = await fetchJobs({ q: nextQ, where: nextWhere, page: 1 });
      setMeta(data);
      setJobs((data.jobs || []).map(mapJobCard).filter(Boolean));
      const params = new URLSearchParams();
      if (nextQ) params.set('q', nextQ);
      if (nextWhere) params.set('where', nextWhere);
      setSearchParams(params, { replace: true });
    } catch (err) {
      setError(err.message || 'Could not load jobs.');
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (authReady) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authReady]);

  const practice = async (jobId) => {
    setBusy(true);
    setError('');
    try {
      const data = await fetchJobPractice(jobId);
      const sessionId = data.session_id;
      if (!sessionId) throw new Error('Practice start did not return a session.');
      const state = {
        candidateId: data.candidate_id,
        skill: (data.skills && data.skills[0]) || 'DSA',
        allSkills: data.skills || [],
        sessionId,
        question: data.question,
        difficulty: data.difficulty,
        round_type: data.round_type || 'technical_short_answer',
        question_context: data.question_context || {},
        config_json: data.config_json || {},
        expires_at: data.expires_at || null,
        round: data.round || 1,
        elo: data.elo || 1200,
        totalRounds: data.total_rounds || (data.round_plan || []).length || 1,
        roundsPerSkill: 1,
      };
      saveInterviewState(state);
      navigate(data.navigate || `/interview/${sessionId}`, { state });
    } catch (err) {
      setError(err.message || 'Could not start practice.');
    } finally {
      setBusy(false);
    }
  };

  if (!authReady) {
    return (
      <main className="min-h-screen bg-[var(--color-surface)] grid place-items-center">
        <p className="text-sm text-[var(--color-ink-muted)]">Checking sign-in…</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[var(--color-surface)] text-[var(--color-ink)]">
      <div className="mx-auto w-full max-w-4xl px-[var(--space-4)] py-[var(--space-6)] sm:px-[var(--space-6)]">
        <AppNav userId={navUser.userId} roleId={navUser.roleId} />

        <header className="mt-8 border-b border-[var(--color-border)] pb-6">
          <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--color-accent)]">Job explorer</p>
          <h1 className="mt-2 text-[length:var(--text-3xl)] font-semibold" style={{ fontFamily: 'var(--font-display)' }}>
            India tech & intern listings
          </h1>
          <p className="mt-3 text-sm leading-6 text-[var(--color-ink-muted)]" data-testid="jobs-disclaimer">
            {meta?.disclaimer ||
              'Listings from Adzuna (India). Apply opens the original site in a new tab. interViv is not affiliated with LinkedIn or Naukri.'}
          </p>
          {meta?.empty_reason && (
            <p className="mt-2 text-sm text-[var(--color-warn)]">{meta.empty_reason}</p>
          )}
        </header>

        {error && (
          <div className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-danger)]/30 bg-[var(--color-danger-soft)] px-4 py-3 text-sm text-[var(--color-danger)]">
            {error}
          </div>
        )}

        <form
          className="mt-6 flex flex-wrap gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            load();
          }}
        >
          <input
            className="min-w-[200px] flex-1 rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2 text-sm"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="what"
          />
          <input
            className="w-40 rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2 text-sm"
            value={where}
            onChange={(e) => setWhere(e.target.value)}
            placeholder="where"
          />
          <button
            type="submit"
            disabled={busy}
            className="rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-5 py-2 text-sm font-semibold text-white disabled:opacity-40"
          >
            {busy ? 'Loading…' : 'Search'}
          </button>
        </form>

        <section className="mt-6 grid gap-4" data-testid="jobs-list">
          {jobs.map((job) => {
            const applyHref = jobApplyHref(job);
            return (
              <article
                key={job.id}
                className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5"
                data-testid="job-card"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-semibold text-[var(--color-ink)]">{job.title}</h2>
                    <p className="mt-1 text-sm text-[var(--color-ink-muted)]">
                      {job.company}
                      {job.location ? ` · ${job.location}` : ''}
                      {job.matchPct != null ? ` · match ${job.matchPct}%` : ''}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {applyHref && (
                      <a
                        href={applyHref}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="rounded-[var(--radius-pill)] border border-[var(--color-border)] px-4 py-2 text-xs font-semibold"
                        data-testid="job-apply"
                      >
                        Apply
                      </a>
                    )}
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => practice(job.id)}
                      className="rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-4 py-2 text-xs font-semibold text-white disabled:opacity-40"
                    >
                      Practice for this role
                    </button>
                  </div>
                </div>
                {job.skills.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {job.skills.map((s) => (
                      <span
                        key={s}
                        className="rounded-md bg-[var(--color-success-soft)] px-2 py-0.5 text-[11px] font-medium text-[var(--color-success)]"
                      >
                        {s}
                      </span>
                    ))}
                  </div>
                )}
              </article>
            );
          })}
          {jobs.length === 0 && !busy && (
            <div className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5 text-sm text-[var(--color-ink-muted)]">
              <p>No jobs in this result set.</p>
              <p className="mt-2">
                Not sure what to search?{' '}
                <Link to="/coach" className="font-semibold text-[var(--color-ink)] underline-offset-2 hover:underline">
                  Ask the coach
                </Link>
                .
              </p>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
