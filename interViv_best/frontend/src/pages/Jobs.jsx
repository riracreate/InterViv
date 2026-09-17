import React, { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import {
  fetchMe,
  fetchJobs,
  fetchJobPrepare,
  fetchJobPractice,
  saveInterviewState,
} from '../lib/api';
import { mapJobCard, jobApplyHref, formatSalary } from '../lib/jobsMapping';
import AppNav from '../components/AppNav';

const ADZUNA_LOGO = 'https://www.adzuna.co.in/images/logo.png';

function AdzunaAttribution({ attribution }) {
  const href = attribution?.jobs_href || attribution?.logo_href || 'https://www.adzuna.co.in/';
  return (
    <p className="mt-3 text-xs text-[var(--color-ink-muted)]" data-testid="jobs-by-adzuna">
      <a href={href} target="_blank" rel="noreferrer noopener" className="underline">
        Jobs
      </a>
      {' by '}
      <a href={href} target="_blank" rel="noreferrer noopener" className="inline-flex items-center gap-1">
        <img
          src={ADZUNA_LOGO}
          alt="Adzuna"
          width={58}
          height={12}
          className="inline-block h-3 w-auto"
          onError={(e) => {
            e.currentTarget.style.display = 'none';
          }}
        />
        <span className="font-semibold text-[var(--color-ink)]">Adzuna</span>
      </a>
    </p>
  );
}

export default function Jobs() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [authReady, setAuthReady] = useState(false);
  const [navUser, setNavUser] = useState({ userId: null, roleId: null });
  const [q, setQ] = useState(searchParams.get('q') || 'software intern OR backend OR data');
  const [where, setWhere] = useState(searchParams.get('where') || 'Pune');
  const [country, setCountry] = useState(searchParams.get('country') || 'in');
  const [page, setPage] = useState(Number(searchParams.get('page') || 1));
  const [jobs, setJobs] = useState([]);
  const [meta, setMeta] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [prepare, setPrepare] = useState(null);
  const [fullJd, setFullJd] = useState('');
  const [draftSkills, setDraftSkills] = useState('');
  const [draftCompany, setDraftCompany] = useState('');
  const [draftRole, setDraftRole] = useState('');

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

  const load = async (nextQ = q, nextWhere = where, nextPage = page, nextCountry = country) => {
    setBusy(true);
    setError('');
    try {
      const data = await fetchJobs({
        q: nextQ,
        where: nextWhere,
        page: nextPage,
        country: nextCountry,
      });
      setMeta(data);
      setJobs((data.jobs || []).map(mapJobCard).filter(Boolean));
      const params = new URLSearchParams();
      if (nextQ) params.set('q', nextQ);
      if (nextWhere) params.set('where', nextWhere);
      if (nextCountry) params.set('country', nextCountry);
      if (nextPage > 1) params.set('page', String(nextPage));
      setSearchParams(params, { replace: true });
    } catch (err) {
      setJobs([]);
      setMeta(null);
      setError(err.message || 'Could not load jobs.');
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (authReady) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authReady]);

  const openPrepare = async (jobId) => {
    setBusy(true);
    setError('');
    try {
      const draft = await fetchJobPrepare(jobId, fullJd ? { full_jd: fullJd } : {});
      setPrepare(draft);
      setDraftSkills((draft.proposed_skills || []).join(', '));
      setDraftCompany(draft.company || '');
      setDraftRole(draft.role || '');
    } catch (err) {
      setError(err.message || 'Could not prepare practice.');
    } finally {
      setBusy(false);
    }
  };

  const confirmPractice = async () => {
    if (!prepare?.job_id) return;
    setBusy(true);
    setError('');
    try {
      const skills = draftSkills
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);
      const data = await fetchJobPractice(prepare.job_id, {
        confirm: true,
        skills,
        blocks: prepare.proposed_blocks,
        company: draftCompany,
        role: draftRole,
        full_jd: fullJd || undefined,
      });
      if (!data.started || !data.session_id) {
        throw new Error('Confirm practice before starting.');
      }
      const sessionId = data.session_id;
      const state = {
        candidateId: data.candidate_id,
        skill: (data.skills && data.skills[0]) || skills[0] || 'DSA',
        allSkills: data.skills || skills,
        sessionId,
        question: data.question,
        difficulty: data.difficulty,
        round_type: data.round_type || 'technical_short_answer',
        block_category: data.block_category || null,
        question_context: data.question_context || {},
        config_json: data.config_json || {},
        expires_at: data.expires_at || null,
        round: data.round || 1,
        elo: data.elo || 1200,
        totalRounds: data.total_rounds || (data.round_plan || []).length || 1,
        roundsPerSkill: 1,
      };
      saveInterviewState(state);
      setPrepare(null);
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
          <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--color-accent)]">
            Job explorer
          </p>
          <h1
            className="mt-2 text-[length:var(--text-3xl)] font-semibold"
            style={{ fontFamily: 'var(--font-display)' }}
          >
            Discover openings
          </h1>
          <p className="mt-3 text-sm leading-6 text-[var(--color-ink-muted)]" data-testid="jobs-disclaimer">
            {meta?.disclaimer ||
              'Listings from Adzuna. View job opens the original listing. Ordinary Practice stays available without a job handoff.'}
          </p>
          {meta?.empty_reason && (
            <p className="mt-2 text-sm text-[var(--color-warn)]" data-testid="jobs-sample-banner">
              {meta.empty_reason}
            </p>
          )}
          {meta?.fetched_at && (
            <p className="mt-2 text-xs text-[var(--color-ink-muted)]" data-testid="jobs-fetched-at">
              Results obtained {meta.fetched_at}
              {meta.cache_hit ? ' (served from cache; provenance unchanged)' : ''}
              {meta.provenance ? ` · source: ${meta.provenance}` : ''}
            </p>
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
            setPage(1);
            load(q, where, 1, country);
          }}
        >
          <input
            className="min-w-[200px] flex-1 rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2 text-sm"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="keywords"
          />
          <input
            className="w-40 rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2 text-sm"
            value={where}
            onChange={(e) => setWhere(e.target.value)}
            placeholder="location"
          />
          <input
            className="w-20 rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2 text-sm uppercase"
            value={country}
            onChange={(e) => setCountry(e.target.value.toLowerCase())}
            placeholder="in"
            maxLength={2}
            title="Adzuna country code (e.g. in, gb, us)"
          />
          <button
            type="submit"
            disabled={busy}
            className="rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-5 py-2 text-sm font-semibold text-white disabled:opacity-40"
          >
            {busy ? 'Loading…' : 'Search'}
          </button>
        </form>

        <p className="mt-3 text-sm">
          <Link to="/practice" className="underline text-[var(--color-ink-muted)]">
            Open Practice without a job
          </Link>
        </p>

        <section className="mt-6 grid gap-4" data-testid="jobs-list">
          {jobs.map((job) => {
            const viewHref = jobApplyHref(job);
            const salary = formatSalary(job);
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
                    {salary && (
                      <p className="mt-1 text-sm text-[var(--color-ink)]" data-testid="job-salary">
                        {salary}
                      </p>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {viewHref && (
                      <a
                        href={viewHref}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="rounded-[var(--radius-pill)] border border-[var(--color-border)] px-4 py-2 text-xs font-semibold"
                        data-testid="job-view"
                      >
                        View job
                      </a>
                    )}
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => openPrepare(job.id)}
                      className="rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-4 py-2 text-xs font-semibold text-white disabled:opacity-40"
                      data-testid="job-prepare"
                    >
                      Prepare for this role
                    </button>
                  </div>
                </div>
                {job.snippet && (
                  <p className="mt-3 text-sm leading-6 text-[var(--color-ink-muted)]">{job.snippet}</p>
                )}
                <AdzunaAttribution attribution={job.attribution} />
              </article>
            );
          })}
        </section>

        <div className="mt-6 flex items-center gap-3">
          <button
            type="button"
            disabled={busy || page <= 1}
            className="rounded-[var(--radius-pill)] border border-[var(--color-border)] px-4 py-2 text-sm disabled:opacity-40"
            onClick={() => {
              const next = Math.max(1, page - 1);
              setPage(next);
              load(q, where, next, country);
            }}
          >
            Previous
          </button>
          <span className="text-sm text-[var(--color-ink-muted)]">Page {page}</span>
          <button
            type="button"
            disabled={busy || jobs.length === 0}
            className="rounded-[var(--radius-pill)] border border-[var(--color-border)] px-4 py-2 text-sm disabled:opacity-40"
            onClick={() => {
              const next = page + 1;
              setPage(next);
              load(q, where, next, country);
            }}
          >
            Next
          </button>
        </div>

        {prepare && (
          <div
            className="fixed inset-0 z-40 grid place-items-center bg-black/40 p-4"
            role="dialog"
            aria-modal="true"
            data-testid="job-prepare-dialog"
          >
            <div className="w-full max-w-lg rounded-[var(--radius-card)] bg-[var(--color-card)] p-5 shadow-lg">
              <h2 className="text-lg font-semibold">Confirm practice setup</h2>
              <p className="mt-2 text-sm text-[var(--color-ink-muted)]">{prepare.note}</p>
              <label className="mt-4 block text-xs font-semibold uppercase tracking-wide">Role</label>
              <input
                className="mt-1 w-full rounded border border-[var(--color-border)] px-3 py-2 text-sm"
                value={draftRole}
                onChange={(e) => setDraftRole(e.target.value)}
              />
              <label className="mt-3 block text-xs font-semibold uppercase tracking-wide">Company</label>
              <input
                className="mt-1 w-full rounded border border-[var(--color-border)] px-3 py-2 text-sm"
                value={draftCompany}
                onChange={(e) => setDraftCompany(e.target.value)}
              />
              <label className="mt-3 block text-xs font-semibold uppercase tracking-wide">
                Skills (comma-separated)
              </label>
              <input
                className="mt-1 w-full rounded border border-[var(--color-border)] px-3 py-2 text-sm"
                value={draftSkills}
                onChange={(e) => setDraftSkills(e.target.value)}
              />
              <label className="mt-3 block text-xs font-semibold uppercase tracking-wide">
                Optional full job description
              </label>
              <textarea
                className="mt-1 w-full rounded border border-[var(--color-border)] px-3 py-2 text-sm"
                rows={4}
                value={fullJd}
                onChange={(e) => setFullJd(e.target.value)}
                placeholder="Paste the full JD if you have it. The listing snippet is incomplete."
              />
              <p className="mt-2 text-xs text-[var(--color-ink-muted)]">
                Blocks proposed: {(prepare.proposed_blocks || []).length}. Scoring and inventory
                rules are unchanged. You can also{' '}
                <Link to="/practice" className="underline">
                  open Practice
                </Link>{' '}
                without this handoff.
              </p>
              <div className="mt-4 flex flex-wrap gap-2 justify-end">
                <button
                  type="button"
                  className="rounded-[var(--radius-pill)] border border-[var(--color-border)] px-4 py-2 text-sm"
                  onClick={() => setPrepare(null)}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={busy}
                  className="rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
                  onClick={confirmPractice}
                  data-testid="job-confirm-practice"
                >
                  Start confirmed practice
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
