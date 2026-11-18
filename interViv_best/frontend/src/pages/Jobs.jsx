import React, { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import {
  fetchMe,
  fetchJobs,
  fetchJobPrepare,
  fetchJobPractice,
  saveInterviewState,
  createCoachConversation,
  patchCoachGoals,
  saveTargetContext,
} from '../lib/api';
import {
  mapJobCard, jobApplyHref, formatSalary,
  jobCoachHandoff, jobLaunchScope, jobPracticeBody, jobSkillKey, jobSkillList, jobStartState,
} from '../lib/jobsMapping';
import PlannedScope from '../components/PlannedScope';
import AppNav from '../components/AppNav';
import AccountGate from '../components/AccountGate';
import { useAccountRetry } from '../lib/useAccountRetry';
import { readScoped, writeScoped } from '../lib/accountStorage';
import { isSavedJob, toggleSavedJob as toggleSavedJobList } from '../lib/savedJobs';
import '../styles/hub.css';

const ADZUNA_LOGO = 'https://www.adzuna.co.in/images/logo.png';

function JobSourceToggle({ source, disabled, onChange }) {
  const greenhouse = source === 'greenhouse';
  return (
    <button
      type="button"
      role="switch"
      aria-checked={greenhouse}
      aria-label="Job source. Adzuna or Greenhouse."
      data-testid="jobs-source-toggle"
      disabled={disabled}
      className={`jobs-source-toggle ${greenhouse ? 'is-greenhouse' : 'is-adzuna'}`}
      onClick={() => onChange(greenhouse ? 'adzuna' : 'greenhouse')}
    >
      <span className="jobs-source-knob" aria-hidden="true" />
      <span className={greenhouse ? '' : 'is-active'}>Adzuna</span>
      <span className={greenhouse ? 'is-active' : ''}>Greenhouse</span>
    </button>
  );
}

function AdzunaAttribution({ attribution }) {
  const href = attribution?.jobs_href || attribution?.logo_href || 'https://www.adzuna.co.in/';
  return (
    <p className="hub-caption" data-testid="jobs-by-adzuna">
      <a href={href} target="_blank" rel="noreferrer noopener" className="hub-text-link" style={{ marginTop: 0 }}>
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
  const { accountError, accountAttempt, retryAccount, onAccountError } = useAccountRetry();
  const [authReady, setAuthReady] = useState(false);
  const [navUser, setNavUser] = useState({ userId: null, roleId: null });
  const [q, setQ] = useState(searchParams.get('q') || 'software intern OR backend OR data');
  const [where, setWhere] = useState(searchParams.get('where') || 'Pune');
  const [country, setCountry] = useState(searchParams.get('country') || 'in');
  const [source, setSource] = useState(
    searchParams.get('source') === 'greenhouse' ? 'greenhouse' : 'adzuna',
  );
  const [page, setPage] = useState(Number(searchParams.get('page') || 1));
  const [jobs, setJobs] = useState([]);
  const [savedJobs, setSavedJobs] = useState([]);
  const [showSaved, setShowSaved] = useState(false);
  const [meta, setMeta] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [prepare, setPrepare] = useState(null);
  const [fullJd, setFullJd] = useState('');
  const [draftSkills, setDraftSkills] = useState('');
  const [draftCompany, setDraftCompany] = useState('');
  const [draftRole, setDraftRole] = useState('');
  // The skills the draft on screen was built for. When the field differs,
  // the preview is refreshed before practice can start.
  const [previewKey, setPreviewKey] = useState('');
  const [previewBusy, setPreviewBusy] = useState(false);
  const [previewError, setPreviewError] = useState('');
  const [previewAttempt, setPreviewAttempt] = useState(0);
  const previewSeq = useRef(0);

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
      .catch((err) => {
        if (!cancelled) onAccountError(err);
      });
    return () => {
      cancelled = true;
    };
  }, [accountAttempt, navigate]);

  const load = async (
    nextQ = q,
    nextWhere = where,
    nextPage = page,
    nextCountry = country,
    nextSource = source,
  ) => {
    setBusy(true);
    setError('');
    try {
      const data = await fetchJobs({
        q: nextQ,
        where: nextWhere,
        page: nextPage,
        country: nextCountry,
        source: nextSource,
      });
      setMeta(data);
      setJobs((data.jobs || []).map(mapJobCard).filter(Boolean));
      const params = new URLSearchParams();
      if (nextQ) params.set('q', nextQ);
      if (nextWhere) params.set('where', nextWhere);
      if (nextCountry) params.set('country', nextCountry);
      if (nextPage > 1) params.set('page', String(nextPage));
      if (nextSource === 'greenhouse') params.set('source', 'greenhouse');
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

  useEffect(() => {
    const saved = readScoped('local', navUser.userId, 'saved-jobs');
    setSavedJobs(Array.isArray(saved) ? saved.filter(job => job && job.id) : []);
  }, [navUser.userId]);

  const toggleSavedJob = (job) => {
    const next = toggleSavedJobList(savedJobs, job);
    if (!writeScoped('local', navUser.userId, 'saved-jobs', next)) {
      setError('Could not save this job on this device.');
      return;
    }
    setSavedJobs(next);
    setError('');
  };

  const openPrepare = async (jobId) => {
    setBusy(true);
    setError('');
    try {
      const draft = await fetchJobPrepare(jobId, fullJd ? { full_jd: fullJd } : {});
      const skillsText = (draft.proposed_skills || []).join(', ');
      previewSeq.current += 1;
      setPrepare(draft);
      setDraftSkills(skillsText);
      setPreviewKey(jobSkillKey(skillsText));
      setPreviewBusy(false);
      setPreviewError('');
      setDraftCompany(draft.company || '');
      setDraftRole(draft.role || '');
    } catch (err) {
      setError(err.message || 'Could not prepare practice.');
    } finally {
      setBusy(false);
    }
  };

  // Editing the skills changes what would be started, so the draft (blocks
  // and planned scope) is rebuilt on the server for the edited list. Only the
  // latest request is applied.
  const prepareJobId = prepare?.job_id;
  useEffect(() => {
    if (!prepareJobId) return undefined;
    const key = jobSkillKey(draftSkills);
    const seq = ++previewSeq.current;
    if (key === previewKey) {
      setPreviewBusy(false);
      setPreviewError('');
      return undefined;
    }
    setPreviewError('');
    if (!key) {
      setPreviewBusy(false);
      return undefined;
    }
    setPreviewBusy(true);
    const timer = setTimeout(() => {
      fetchJobPrepare(prepareJobId, { skills: jobSkillList(draftSkills) })
        .then((draft) => {
          if (seq !== previewSeq.current) return;
          setPrepare(draft);
          setPreviewKey(key);
          setPreviewBusy(false);
        })
        .catch((err) => {
          if (seq !== previewSeq.current) return;
          setPreviewError(err.message || 'the server did not answer.');
          setPreviewBusy(false);
        });
    }, 400);
    return () => clearTimeout(timer);
    // previewKey is read, not watched: it changes only when a refresh lands.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prepareJobId, draftSkills, previewAttempt]);

  const startState = jobStartState({
    draft: prepare, skillsText: draftSkills, previewKey, previewBusy, previewError,
  });
  // The panel is dimmed only while it describes an older list of skills.
  const previewStale = previewBusy || jobSkillKey(draftSkills) !== previewKey;

  const confirmPractice = async () => {
    if (!prepare?.job_id || !startState.canStart) return;
    setBusy(true);
    setError('');
    try {
      // The skills and blocks of the previewed draft, not the raw field.
      const skills = prepare.proposed_skills || [];
      const data = await fetchJobPractice(prepare.job_id, jobPracticeBody(prepare, {
        company: draftCompany,
        role: draftRole,
        fullJd,
      }));
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
      <main className="hub-page">
        <div className="hub-container">
          <AccountGate error={accountError} onRetry={retryAccount} />
        </div>
      </main>
    );
  }

  return (
    <main className="hub-page">
      <div className="hub-container">
        <AppNav userId={navUser.userId} roleId={navUser.roleId} />

        <header className="hub-page-hero">
          <p className="hub-eyebrow">Job explorer</p>
          <h1>Discover openings</h1>
          <p data-testid="jobs-disclaimer">
            {meta?.disclaimer ||
              'Listings from Adzuna. View job opens the original listing. Ordinary Practice stays available without a job handoff.'}
          </p>
          {meta?.note && (
            <p className="hub-notice hub-notice-info" data-testid="jobs-source-note" role="status">
              {meta.note}
            </p>
          )}
          {meta?.empty_reason && (
            <p className="hub-notice hub-notice-warn" data-testid="jobs-sample-banner" role="status">
              {meta.empty_reason}
            </p>
          )}
          <JobSourceToggle
            source={source}
            disabled={busy}
            onChange={(next) => {
              setSource(next);
              setPage(1);
              load(q, where, 1, country, next);
            }}
          />
          {meta?.fetched_at && (
            <p className="hub-caption" data-testid="jobs-fetched-at">
              Results obtained {meta.fetched_at}
              {meta.cache_hit ? ' (served from cache; provenance unchanged)' : ''}
              {meta.provenance ? ` · source: ${meta.provenance}` : ''}
            </p>
          )}
        </header>

        {error && (
          <div className="hub-error" role="alert">
            {error}
          </div>
        )}

        <form
          className="hub-toolbar"
          onSubmit={(e) => {
            e.preventDefault();
            setPage(1);
            load(q, where, 1, country, source);
          }}
        >
          <input
            className="hub-field"
            style={{ flex: '1 1 200px', minWidth: 160 }}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="keywords"
            aria-label="Job keywords"
          />
          <input
            className="hub-field"
            style={{ flex: '0 1 10rem' }}
            value={where}
            onChange={(e) => setWhere(e.target.value)}
            placeholder="location"
            aria-label="Location"
          />
          <input
            className="hub-field"
            style={{ flex: '0 0 4.5rem', textTransform: 'uppercase' }}
            value={country}
            onChange={(e) => setCountry(e.target.value.toLowerCase())}
            placeholder="in"
            maxLength={2}
            title="Adzuna country code (e.g. in, gb, us)"
            aria-label="Country code"
          />
          <button type="submit" disabled={busy} className="hub-button hub-button-primary">
            {busy ? 'Loading…' : 'Search'}
          </button>
        </form>

        <p>
          <Link to="/practice" className="hub-text-link" style={{ marginTop: 0 }}>
            Open Practice without a job
          </Link>
        </p>

        <div className="iv-job-view-toggle"><button type="button" aria-pressed={!showSaved} onClick={() => setShowSaved(false)}>Search results</button><button type="button" aria-pressed={showSaved} onClick={() => setShowSaved(true)}>Saved jobs ({savedJobs.length})</button></div>
        {showSaved && <p className="hub-caption">Saved on this device for your account. Listings and preparation links may expire.</p>}
        <section className="hub-list" data-testid="jobs-list">
          {!busy && (showSaved ? savedJobs : jobs).length === 0 && !error && (
            <div className="hub-empty-inline" data-testid="jobs-empty">
              <h3>{showSaved ? 'No saved jobs yet' : 'No listings for this search'}</h3>
              <p>{showSaved ? 'Save a listing to find it here later on this device.' : 'Try different keywords, location, or country — or open Practice without a job.'}</p>
            </div>
          )}
          {(showSaved ? savedJobs : jobs).map((job) => {
            const viewHref = jobApplyHref(job);
            const salary = formatSalary(job);
            const saved = isSavedJob(savedJobs, job);
            return (
              <article key={job.id} className="hub-card" data-testid="job-card">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 style={{ fontSize: 'var(--text-lg)', fontWeight: 600 }}>{job.title}</h2>
                    <p className="hub-caption" style={{ marginTop: 4 }}>
                      {job.company}
                      {job.location ? ` · ${job.location}` : ''}
                      {job.matchPct != null ? ` · match ${job.matchPct}%` : ''}
                    </p>
                    {salary && (
                      <p className="mt-1 text-sm" data-testid="job-salary">
                        {salary}
                      </p>
                    )}
                    {job.snippet && (
                      <p className="mt-3 text-sm leading-6 text-[var(--color-ink-muted)]">
                        {job.snippet}
                        <span className="hub-caption"> · listing snippet (incomplete)</span>
                      </p>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button type="button" className="hub-button" aria-pressed={saved} onClick={() => toggleSavedJob(job)}
                      aria-label={`${saved ? 'Remove saved' : 'Save'} ${job.title}`}>{saved ? 'Saved ✓' : 'Save'}</button>
                    {viewHref && (
                      <a
                        href={viewHref}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="hub-button"
                        data-testid="job-view"
                      >
                        View job
                      </a>
                    )}
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => openPrepare(job.id)}
                      className="hub-button hub-button-primary"
                      data-testid="job-prepare"
                    >
                      Prepare for this role
                    </button>
                  </div>
                </div>
                {['sample', 'fixture'].includes(job.provenance) ? (
                  <p className="hub-caption" data-testid="jobs-sample-listing">
                    Sample listing — fictional company, not a real opening
                  </p>
                ) : job.provenance === 'greenhouse' ? (
                  <p className="hub-caption" data-testid="jobs-by-greenhouse">
                    Public Greenhouse board
                  </p>
                ) : (
                  <AdzunaAttribution attribution={job.attribution} />
                )}
              </article>
            );
          })}
        </section>

        {!showSaved && <div className="hub-toolbar" style={{ alignItems: 'center' }}>
          <button
            type="button"
            disabled={busy || page <= 1}
            className="hub-button"
            onClick={() => {
              const next = Math.max(1, page - 1);
              setPage(next);
              load(q, where, next, country, source);
            }}
          >
            Previous
          </button>
          <span className="hub-caption">Page {page}</span>
          <button
            type="button"
            disabled={busy || jobs.length === 0}
            className="hub-button"
            onClick={() => {
              const next = page + 1;
              setPage(next);
              load(q, where, next, country, source);
            }}
          >
            Next
          </button>
        </div>}

        {prepare && (
          <div
            className="hub-modal-backdrop"
            role="dialog"
            aria-modal="true"
            aria-labelledby="job-prepare-title"
            data-testid="job-prepare-dialog"
          >
            <div className="hub-modal">
              <h2 id="job-prepare-title" style={{ fontFamily: 'var(--font-display)', fontSize: '1.6rem' }}>
                Confirm practice setup
              </h2>
              <p className="mt-2 text-sm text-[var(--color-ink-muted)]">{prepare.note}</p>
              {(prepare.proposed_blocks || []).length > 0 && (
                <p className="hub-caption" style={{ marginTop: 8 }}>
                  Proposed blocks: {(prepare.proposed_blocks || []).map((b) => b.category || b.round_type || 'block').join(', ')}
                  {' '}({(prepare.proposed_blocks || []).length})
                </p>
              )}
              <label className="hub-eyebrow" style={{ display: 'block', marginTop: 16 }} htmlFor="job-draft-role">
                Role
              </label>
              <input
                id="job-draft-role"
                className="hub-field"
                value={draftRole}
                onChange={(e) => setDraftRole(e.target.value)}
              />
              <label className="hub-eyebrow" style={{ display: 'block', marginTop: 12 }} htmlFor="job-draft-company">
                Company
              </label>
              <input
                id="job-draft-company"
                className="hub-field"
                value={draftCompany}
                onChange={(e) => setDraftCompany(e.target.value)}
              />
              <label className="hub-eyebrow" style={{ display: 'block', marginTop: 12 }} htmlFor="job-draft-skills">
                Skills (comma-separated)
              </label>
              <input
                id="job-draft-skills"
                className="hub-field"
                value={draftSkills}
                onChange={(e) => setDraftSkills(e.target.value)}
              />
              <div style={{ opacity: previewStale ? 0.55 : 1 }} aria-busy={previewStale}>
                <PlannedScope
                  scope={jobSkillList(draftSkills).length ? jobLaunchScope(prepare) : null}
                  notCoveredHint="Job practice asks at most three free-text questions."
                  countFixed
                />
              </div>
              {!startState.canStart && (
                <div
                  className={`app-notice ${previewError ? 'app-notice-error' : 'app-notice-warn'}`}
                  role="status"
                  data-testid="job-start-blocked"
                >
                  {startState.reason}{' '}
                  {previewError && (
                    <button
                      type="button"
                      className="hub-text-link"
                      style={{ marginTop: 0 }}
                      onClick={() => setPreviewAttempt((n) => n + 1)}
                    >
                      Retry
                    </button>
                  )}
                </div>
              )}
              <label className="hub-eyebrow" style={{ display: 'block', marginTop: 12 }} htmlFor="job-full-jd">
                Optional full job description
              </label>
              <textarea
                id="job-full-jd"
                className="hub-field"
                rows={4}
                value={fullJd}
                onChange={(e) => setFullJd(e.target.value)}
                placeholder="Paste the full JD if you have it. The listing snippet is incomplete."
              />
              <p className="hub-caption" style={{ marginTop: 8 }}>
                Scoring and inventory rules are unchanged. You can also{' '}
                <Link to="/practice" className="hub-text-link" style={{ marginTop: 0 }}>
                  open Practice
                </Link>{' '}
                without this handoff.
              </p>
              <div className="hub-toolbar" style={{ justifyContent: 'flex-end' }}>
                <button type="button" className="hub-button" onClick={() => setPrepare(null)}>
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={busy}
                  className="hub-button"
                  data-testid="job-coach-handoff"
                  onClick={async () => {
                    try {
                      setBusy(true);
                      const handoff = jobCoachHandoff({
                        prepare, draftSkills, draftRole, draftCompany, fullJd,
                      });
                      await saveTargetContext(handoff.target).catch(() => {});
                      const created = await createCoachConversation();
                      const cid = created.conversation?.conversation_id;
                      if (cid) {
                        await patchCoachGoals(cid, handoff.goals);
                      }
                      setPrepare(null);
                      navigate('/coach');
                    } catch (err) {
                      setError(err.message || 'Could not open Coach with this job context.');
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  Continue in Coach
                </button>
                <button
                  type="button"
                  disabled={busy || !startState.canStart}
                  className="hub-button hub-button-primary"
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
