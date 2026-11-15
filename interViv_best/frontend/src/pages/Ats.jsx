import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { CheckCircle2, FileText, ScanSearch, Sparkles, UploadCloud } from 'lucide-react';
import {
  fetchMe,
  fetchCompanies,
  uploadResume,
  scoreAts,
  fetchAtsRuns,
  fetchTargetContext,
} from '../lib/api';
import { mapAtsResultToView } from '../lib/atsMapping';
import ResourceLinks from '../components/ResourceLinks';
import AppNav from '../components/AppNav';
import AccountGate from '../components/AccountGate';
import { useAccountRetry } from '../lib/useAccountRetry';
import { MAX_RESUME_LABEL, resumeFileError } from '../lib/resumeUpload';

export default function AtsChecker() {
  const navigate = useNavigate();
  const { accountError, accountAttempt, retryAccount, onAccountError } = useAccountRetry();
  const [authReady, setAuthReady] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [candidateId, setCandidateId] = useState('');
  const [fileName, setFileName] = useState('');
  const [skills, setSkills] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [roleId, setRoleId] = useState('');
  const [jdText, setJdText] = useState('');
  const [mode, setMode] = useState('role'); // role | jd
  const [fieldsTouched, setFieldsTouched] = useState(false);
  const [result, setResult] = useState(null);
  const [lastTotal, setLastTotal] = useState(null);
  const [navUser, setNavUser] = useState({ userId: null, roleId: null });

  useEffect(() => {
    let cancelled = false;
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

  useEffect(() => {
    if (!authReady) return undefined;
    let cancelled = false;
    // Shared target context wins over the first-role default; typed
    // input is never overridden (prefill applies to empty fields only).
    fetchTargetContext()
      .then((data) => {
        if (cancelled || !data.target) return null;
        if (data.target.resume_ref) setCandidateId((prev) => prev || data.target.resume_ref);
        if (data.target.jd_text && !fieldsTouched) {
          setJdText(data.target.jd_text);
          setMode('jd');
        }
        return data.target.role_id || null;
      })
      .catch(() => null)
      .then((targetRole) => {
        if (cancelled) return;
        fetchCompanies()
          .then((data) => {
            if (cancelled) return;
            setCompanies(data.companies || []);
            if (targetRole) {
              setRoleId((prev) => prev || targetRole);
              return;
            }
            const firstRole = data.companies?.[0]?.roles?.[0]?.id;
            if (firstRole) setRoleId((prev) => prev || firstRole);
          })
          .catch(() => {});
      });
    fetchAtsRuns()
      .then((data) => {
        if (cancelled) return;
        const run = data.runs?.[0];
        if (run) setLastTotal(run.total);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [authReady]);

  const roleOptions = [];
  for (const company of companies) {
    for (const role of company.roles || []) {
      roleOptions.push({
        id: role.id,
        label: `${company.name} — ${role.title}`,
      });
    }
  }

  const onUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const problem = resumeFileError(file);
    if (problem) { setError(problem); return; }
    setBusy(true);
    setError('');
    try {
      const data = await uploadResume(file);
      setCandidateId(data.candidate_id);
      setSkills(data.skills || []);
      setFileName(file.name);
    } catch (err) {
      setError(err.message || 'Upload failed.');
    } finally {
      setBusy(false);
    }
  };

  const onScore = async () => {
    if (!candidateId) {
      setError('Upload a resume PDF first.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const body =
        mode === 'role'
          ? { candidate_id: candidateId, role_id: roleId }
          : { candidate_id: candidateId, jd_text: jdText };
      const data = await scoreAts(body);
      const view = mapAtsResultToView(data);
      setResult(view);
      setLastTotal(view?.total ?? null);
    } catch (err) {
      setError(err.message || 'ATS scoring failed.');
    } finally {
      setBusy(false);
    }
  };

  if (!authReady) {
    return (
      <main className="min-h-screen bg-[var(--color-surface)] grid place-items-center">
        <AccountGate error={accountError} onRetry={retryAccount} />
      </main>
    );
  }

  const firstMissing = result?.missingSkills?.[0];

  return (
    <main className="min-h-screen bg-[var(--color-surface)] text-[var(--color-ink)]">
      <div className="app-container">
        <AppNav userId={navUser.userId} roleId={navUser.roleId} />

        <header className="app-page-hero">
          <p className="iv-page-kicker">Career / Resume check</p>
          <h1 className="mt-2 text-[length:var(--text-3xl)] font-semibold" style={{ fontFamily: 'var(--font-display)' }}>
            Make your resume work harder.
          </h1>
          <p className="mt-3 text-sm leading-6 text-[var(--color-ink-muted)]">
            See how clearly your resume presents your experience and how its skills match a role or job description.
          </p>
          {lastTotal != null && (
            <p className="mt-2 text-sm text-[var(--color-ink)]">
              Last ATS total: <strong>{Math.round(lastTotal)}</strong>
            </p>
          )}
        </header>

        {error && (
          <div role="alert" className="mt-4 rounded-[var(--radius-card)] border border-[var(--color-danger)]/30 bg-[var(--color-danger-soft)] px-4 py-3 text-sm text-[var(--color-danger)]">
            {error}
          </div>
        )}

        <div className="iv-ats-layout">
        <section className="iv-ats-form mt-6 space-y-4 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5" aria-labelledby="resume-upload-heading">
          <div><p className="iv-page-kicker">Step 01</p><h2 id="resume-upload-heading">Add your resume</h2><p>Choose a text-based PDF to get started.</p></div>
          <label className="iv-file-upload">
            <input
              type="file"
              accept="application/pdf,.pdf"
              className="sr-only"
              onChange={onUpload}
              disabled={busy}
            />
            <span className="iv-quick-icon"><UploadCloud size={21} aria-hidden="true" /></span>
            <strong>{fileName || (candidateId ? 'Use saved resume or choose another' : 'Choose a PDF resume')}</strong>
            <span>PDF only, up to {MAX_RESUME_LABEL}.</span>
          </label>
          {candidateId && (
            <p className="text-xs text-[var(--color-ink-muted)]">
              <CheckCircle2 size={14} className="inline" aria-hidden="true" /> Resume ready
              {skills.length > 0 ? ` · skills: ${skills.slice(0, 8).join(', ')}` : ''}
            </p>
          )}

          <div className="iv-ats-step"><p className="iv-page-kicker">Step 02</p><h2>Choose what to compare</h2></div>
          <div className="flex gap-4 text-sm">
            <label className="flex items-center gap-2">
              <input type="radio" checked={mode === 'role'} onChange={() => setMode('role')} />
              Choose a role
            </label>
            <label className="flex items-center gap-2">
              <input type="radio" checked={mode === 'jd'} onChange={() => setMode('jd')} />
              Paste a job description
            </label>
          </div>

          {mode === 'role' ? (
            <label className="block text-sm">
              Role
              <select
                className="mt-1 w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                value={roleId}
                onChange={(e) => {
                  setFieldsTouched(true);
                  setRoleId(e.target.value);
                }}
              >
                {roleOptions.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.label}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <label className="block text-sm">
              Job description
              <textarea
                className="mt-1 min-h-[120px] w-full rounded-[var(--radius-card)] border border-[var(--color-border)] px-3 py-2"
                value={jdText}
                onChange={(e) => {
                  setFieldsTouched(true);
                  setJdText(e.target.value);
                }}
                placeholder="Paste the job description here…"
              />
            </label>
          )}

          <button
            type="button"
            disabled={busy}
            onClick={onScore}
            className="rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
          >
            {busy ? 'Working…' : 'Check my resume'}
          </button>
        </section>
        <aside className="iv-ats-aside"><p className="iv-page-kicker">A clearer picture</p><h2>What you'll see</h2>
          <div><span className="iv-quick-icon"><ScanSearch size={19} /></span><p><strong>Readability &amp; structure</strong><br />See whether key resume sections can be read.</p></div>
          <div><span className="iv-quick-icon"><FileText size={19} /></span><p><strong>Role alignment</strong><br />Find skills mentioned and skills to review.</p></div>
          <div><span className="iv-quick-icon"><Sparkles size={19} /></span><p><strong>Practical next steps</strong><br />Use the feedback to make honest improvements.</p></div>
          <p className="iv-ats-footnote">This is a preparation guide, not an employer's ATS score or a hiring prediction. Some PDF layouts may not be read completely.</p>
        </aside>
        </div>

        {result && (
          <section className="mt-6 space-y-4" data-testid="ats-result">
            {result.reuploadRecommended && (
              <div
                role="status"
                data-testid="ats-reupload"
                className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-4 text-sm text-[var(--color-ink)]"
              >
                This resume was saved before layout and section checks were stored, so
                those parts could not be measured. Upload the PDF again for a complete score.
              </div>
            )}
            <div className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-6 text-center">
              <p className="text-xs uppercase tracking-[0.16em] text-[var(--color-ink-muted)]">ATS total</p>
              <p className="mt-2 text-5xl font-semibold text-[var(--color-ink)]" style={{ fontFamily: 'var(--font-display)' }}>
                {Math.round(result.total)}
              </p>
            </div>

            <div className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
              <h2 className="text-sm font-semibold uppercase tracking-[0.12em] text-[var(--color-accent)]">Components</h2>
              <ul className="mt-3 space-y-2">
                {result.components.map((c) => (
                  <li key={c.key} className="flex items-center justify-between text-sm">
                    <span>
                      {c.label}{' '}
                      <span className="text-[var(--color-ink-muted)]">×{c.weight}</span>
                    </span>
                    <span className="font-semibold">{Math.round(c.score)}</span>
                  </li>
                ))}
              </ul>
            </div>

            {result.flags.length > 0 && (
              <div className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
                <h2 className="text-sm font-semibold uppercase tracking-[0.12em] text-[var(--color-accent)]">Flags</h2>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-[var(--color-ink-muted)]">
                  {result.flags.map((f) => (
                    <li key={f}>{f}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
                <h2 className="text-sm font-semibold">Present</h2>
                <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
                  {result.presentSkills.join(', ') || '—'}
                </p>
              </div>
              <div className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-card)] p-5">
                <h2 className="text-sm font-semibold">Missing</h2>
                <p className="mt-2 text-sm text-[var(--color-ink-muted)]">
                  {result.missingSkills.join(', ') || '—'}
                </p>
              </div>
            </div>

            {result.unsubstantiatedSkills?.length > 0 && (
              <div className="rounded-[var(--radius-card)] border border-[var(--color-warn)]/30 bg-[var(--color-warn-soft)] p-5" data-testid="ats-unsubstantiated">
                <h2 className="text-sm font-semibold">Listed but not shown in Experience or Projects</h2>
                <p className="mt-2 text-sm text-[var(--color-ink)]">{result.unsubstantiatedSkills.join(', ')}</p>
                <p className="mt-2 text-xs text-[var(--color-ink-muted)]">
                  Expect interviewers to probe these. Add a bullet that shows where you used each one. This does not change the score.
                </p>
              </div>
            )}

            {firstMissing && (
              <div className="flex flex-wrap gap-3">
                <Link
                  to={`/practice?mode=full&skill=${encodeURIComponent(firstMissing)}`}
                  className="rounded-[var(--radius-pill)] bg-[var(--color-ink)] px-4 py-2 text-sm font-semibold text-white"
                >
                  Practice {firstMissing}
                </Link>
                <Link
                  to={`/resources?skill_id=${encodeURIComponent(firstMissing)}`}
                  className="rounded-[var(--radius-pill)] border border-[var(--color-border)] px-4 py-2 text-sm font-semibold text-[var(--color-ink)]"
                >
                  Resources for {firstMissing}
                </Link>
              </div>
            )}
            {firstMissing && (
              <ResourceLinks skillId={firstMissing} heading={`Resources for ${firstMissing}`} />
            )}
          </section>
        )}
      </div>
    </main>
  );
}
