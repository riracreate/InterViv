import React, { useEffect, useMemo, useState } from 'react';
import AppNav from '../components/AppNav';
import {
  fetchAdminBundles,
  fetchAdminBundleVersion,
  postAdminBundleDecision,
  submitAdminBundleForReview,
} from '../lib/api';
import {
  DIFFICULTY_OPTIONS,
  REVIEWER_CONCEPT_GUIDANCE,
  REVIEW_CHECKLIST_ITEMS,
  adminErrorNotice,
  availableDecisions,
  buildDecisionPayload,
  canSubmitForReview,
  emptyChecklist,
  formatAutoCheckSummary,
  questionWordTerms,
  validateReviewForm,
} from '../lib/bundleReview';

export default function BundleReview({
  initialBundles = null,
  initialDetail = null,
  initialStatusFilter = 'all',
  initialAccessError = '',
}) {
  const [bundles, setBundles] = useState(() => initialBundles || []);
  const [statusFilter, setStatusFilter] = useState(initialStatusFilter);
  const [selected, setSelected] = useState(() => {
    if (initialDetail) {
      return { bundleId: initialDetail.bundle_id, version: initialDetail.version };
    }
    const firstBundle = (initialBundles || [])[0];
    const firstVersion = firstBundle && firstBundle.versions && firstBundle.versions[0];
    return firstVersion ? { bundleId: firstBundle.bundle_id, version: firstVersion.version } : null;
  });
  const [detail, setDetail] = useState(initialDetail);
  const [loadingList, setLoadingList] = useState(initialBundles === null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [busy, setBusy] = useState(false);
  const [accessError, setAccessError] = useState(initialAccessError);
  const [actionError, setActionError] = useState('');
  const [actionNotice, setActionNotice] = useState('');
  const [checklist, setChecklist] = useState(() => emptyChecklist(false));
  const [difficulty, setDifficulty] = useState('');
  const [reasons, setReasons] = useState('');
  const [submitReason, setSubmitReason] = useState('');

  async function loadQueue() {
    setLoadingList(true);
    setAccessError('');
    try {
      const data = await fetchAdminBundles();
      const rows = Array.isArray(data?.bundles) ? data.bundles : [];
      setBundles(rows);
      if (!selected && rows.length > 0 && rows[0].versions?.length > 0) {
        setSelected({ bundleId: rows[0].bundle_id, version: rows[0].versions[0].version });
      }
    } catch (err) {
      setAccessError(adminErrorNotice(err));
    } finally {
      setLoadingList(false);
    }
  }

  async function loadVersionDetail(bundleId, version) {
    setLoadingDetail(true);
    setActionError('');
    try {
      const data = await fetchAdminBundleVersion(bundleId, version);
      setDetail(data);
    } catch (err) {
      setActionError(err?.message || 'Unable to load bundle version.');
    } finally {
      setLoadingDetail(false);
    }
  }

  useEffect(() => {
    if (initialBundles !== null) return;
    loadQueue();
  }, []);

  useEffect(() => {
    if (!selected) return;
    if (
      initialDetail &&
      initialDetail.bundle_id === selected.bundleId &&
      Number(initialDetail.version) === Number(selected.version) &&
      detail === initialDetail
    ) {
      return;
    }
    loadVersionDetail(selected.bundleId, selected.version);
  }, [selected?.bundleId, selected?.version]);

  const versionRows = useMemo(() => {
    const out = [];
    for (const bundle of bundles) {
      for (const ver of bundle.versions || []) {
        if (statusFilter === 'all' || ver.status === statusFilter) {
          out.push({
            bundleId: bundle.bundle_id,
            skill: bundle.skill,
            topic: bundle.topic,
            ...ver,
          });
        }
      }
    }
    return out;
  }, [bundles, statusFilter]);

  const selectedSummary = useMemo(
    () =>
      selected
        ? versionRows.find(
            (r) => r.bundleId === selected.bundleId && Number(r.version) === Number(selected.version)
          ) || null
        : null,
    [versionRows, selected]
  );

  async function handleSubmitForReview() {
    if (!detail) return;
    setBusy(true);
    setActionError('');
    setActionNotice('');
    try {
      await submitAdminBundleForReview(
        detail.bundle_id,
        detail.version,
        submitReason.trim() || 'Submitted from admin review queue.'
      );
      setActionNotice(`Submitted ${detail.bundle_id} v${detail.version} for review.`);
      await Promise.all([loadQueue(), loadVersionDetail(detail.bundle_id, detail.version)]);
    } catch (err) {
      setActionError(err?.message || 'Submit for review failed.');
    } finally {
      setBusy(false);
    }
  }

  async function handleDecision(decision) {
    if (!detail) return;
    const validationErr = validateReviewForm({ decision, checklist, reasons, difficulty });
    if (validationErr) {
      setActionError(validationErr);
      return;
    }
    setBusy(true);
    setActionError('');
    setActionNotice('');
    try {
      const payload = buildDecisionPayload({
        contentHash: detail.content_hash,
        decision,
        checklist,
        reasons,
        difficulty,
      });
      const res = await postAdminBundleDecision(detail.bundle_id, detail.version, payload);
      setActionNotice(`Recorded "${decision}" — status is now "${res?.version?.status || 'updated'}".`);
      setReasons('');
      await Promise.all([loadQueue(), loadVersionDetail(detail.bundle_id, detail.version)]);
    } catch (err) {
      setActionError(err?.message || 'Failed to record review decision.');
    } finally {
      setBusy(false);
    }
  }

  const content = detail?.content || {};
  const autoCheck = formatAutoCheckSummary(detail?.attribution);
  const decisionChoices = availableDecisions(detail);

  return (
    <div className="min-h-screen bg-[var(--bg-canvas)] text-[var(--ink)]">
      <AppNav />
      <main className="mx-auto max-w-6xl px-4 py-8">
        <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold">Bundle Review Queue</h1>
            <p className="text-sm text-[var(--muted)]">
              Admin human review requires two distinct reviewers (reviewer != author) behind ENABLE_ADMIN_ENDPOINTS.
            </p>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <span>Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded border border-[var(--border)] bg-[var(--surface)] px-2.5 py-1.5"
            >
              <option value="all">all</option>
              <option value="auto_checked">auto_checked</option>
              <option value="draft">draft</option>
              <option value="in_review">in_review</option>
              <option value="reviewed">reviewed</option>
              <option value="rejected">rejected</option>
            </select>
          </label>
        </header>

        {accessError ? (
          <div className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-900">
            {accessError}
          </div>
        ) : (
          <div className="grid gap-6 lg:grid-cols-3">
            <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 lg:col-span-1">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
                Versions ({versionRows.length})
              </h2>
              {loadingList ? (
                <p className="text-sm text-[var(--muted)]">Loading bundles...</p>
              ) : versionRows.length === 0 ? (
                <p className="text-sm text-[var(--muted)]">No bundle versions match this filter.</p>
              ) : (
                <ul className="space-y-2">
                  {versionRows.map((row) => {
                    const isSelected =
                      selected &&
                      selected.bundleId === row.bundleId &&
                      Number(selected.version) === Number(row.version);
                    return (
                      <li key={`${row.bundleId}@${row.version}`}>
                        <button
                          type="button"
                          onClick={() => setSelected({ bundleId: row.bundleId, version: row.version })}
                          className={`w-full rounded border px-3 py-2 text-left text-sm transition ${
                            isSelected
                              ? 'border-[var(--ink)] bg-[var(--bg-canvas)] font-medium'
                              : 'border-[var(--border)] hover:bg-[var(--bg-canvas)]'
                          }`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="truncate">{row.bundleId}</span>
                            <span className="rounded bg-black/5 px-1.5 py-0.5 text-xs">
                              v{row.version} · {row.status}
                            </span>
                          </div>
                          <div className="mt-1 text-xs text-[var(--muted)]">
                            {row.skill} — {row.topic}
                          </div>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>

            <section className="space-y-5 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5 lg:col-span-2">
              {loadingDetail ? (
                <p className="text-sm text-[var(--muted)]">Loading version details...</p>
              ) : !detail ? (
                <p className="text-sm text-[var(--muted)]">Select a bundle version to inspect and review.</p>
              ) : (
                <>
                  <div className="flex flex-wrap items-start justify-between gap-2 border-b border-[var(--border)] pb-3">
                    <div>
                      <h2 className="text-lg font-semibold">
                        {detail.bundle_id} (v{detail.version})
                      </h2>
                      <p className="text-xs text-[var(--muted)]">
                        Status: <strong>{detail.status}</strong> · Source: {detail.source || '—'}
                        {selectedSummary?.author_id ? ` · Author: ${selectedSummary.author_id}` : ''} · Hash:{' '}
                        <code>{String(detail.content_hash || '').slice(0, 12)}</code>
                      </p>
                    </div>
                    <div className="text-xs text-[var(--muted)]">
                      Approvals: {detail.distinct_approvers ?? 0} · Rejects: {detail.distinct_rejecters ?? 0}
                      {detail.needs_adjudication ? ' · Needs 3rd-reviewer adjudication' : ''}
                    </div>
                  </div>

                  {actionError && (
                    <div className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-900">
                      {actionError}
                    </div>
                  )}
                  {actionNotice && (
                    <div className="rounded border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
                      {actionNotice}
                    </div>
                  )}

                  <div className="space-y-2">
                    <h3 className="text-sm font-semibold">Question</h3>
                    <p className="rounded border border-[var(--border)] bg-[var(--bg-canvas)] p-3 text-sm">
                      {content.question}
                    </p>
                  </div>

                  <div className="space-y-2">
                    <h3 className="text-sm font-semibold">Hidden Reference Answer</h3>
                    <p className="rounded border border-[var(--border)] bg-[var(--bg-canvas)] p-3 text-sm whitespace-pre-wrap">
                      {content.reference_answer}
                    </p>
                  </div>

                  <div className="space-y-2">
                    <h3 className="text-sm font-semibold">
                      Required Concepts ({(content.required_concepts || []).length})
                    </h3>
                    <p className="rounded border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                      {REVIEWER_CONCEPT_GUIDANCE}
                    </p>
                    <ul className="space-y-2">
                      {(content.required_concepts || []).map((concept) => (
                        <li
                          key={concept.id}
                          className="rounded border border-[var(--border)] bg-[var(--bg-canvas)] p-3 text-sm"
                        >
                          <div className="font-medium">
                            {concept.id}: {concept.descriptor || concept.description}
                          </div>
                          {Array.isArray(concept.aliases) && concept.aliases.length > 0 && (
                            <div className="mt-1 text-xs text-[var(--muted)]">
                              Aliases: {concept.aliases.join(', ')}
                            </div>
                          )}
                          {questionWordTerms(content.question, concept).length > 0 && (
                            <div className="mt-1 text-xs font-medium text-red-700">
                              Question words used as id/alias:{' '}
                              {questionWordTerms(content.question, concept).join(', ')}
                            </div>
                          )}
                          {Array.isArray(concept.expected_propositions) &&
                            concept.expected_propositions.length > 0 && (
                              <ul className="mt-1 list-disc pl-5 text-xs">
                                {concept.expected_propositions.map((prop, pIdx) => (
                                  <li key={pIdx}>{prop}</li>
                                ))}
                              </ul>
                            )}
                          {Array.isArray(concept.positive_examples) &&
                            concept.positive_examples.length > 0 && (
                              <div className="mt-1 text-xs">
                                <div className="text-[var(--muted)]">Positive examples:</div>
                                <ul className="list-disc pl-5">
                                  {concept.positive_examples.map((ex, eIdx) => (
                                    <li key={eIdx}>{ex}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <h3 className="text-sm font-semibold">
                        Misconceptions ({(content.misconceptions || []).length})
                      </h3>
                      {(content.misconceptions || []).length === 0 ? (
                        <p className="text-xs text-[var(--muted)]">None listed.</p>
                      ) : (
                        <ul className="space-y-2 text-xs">
                          {(content.misconceptions || []).map((m) => (
                            <li key={m.id} className="rounded border border-[var(--border)] p-2">
                              <div className="font-medium">
                                {m.id}: {m.description}
                              </div>
                              {Array.isArray(m.candidate_patterns) && m.candidate_patterns.length > 0 && (
                                <div className="mt-1 text-[var(--muted)]">
                                  Patterns: {m.candidate_patterns.join(' | ')}
                                </div>
                              )}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>

                    <div className="space-y-2">
                      <h3 className="text-sm font-semibold">
                        Follow-ups ({(content.followups || []).length})
                      </h3>
                      {(content.followups || []).length === 0 ? (
                        <p className="text-xs text-[var(--muted)]">None listed.</p>
                      ) : (
                        <ul className="space-y-2 text-xs">
                          {(content.followups || []).map((fu, idx) => (
                            <li key={idx} className="rounded border border-[var(--border)] p-2">
                              <div>{fu.prompt}</div>
                              <div className="mt-1 text-[var(--muted)]">
                                Targets: {fu.targets_concept}
                              </div>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>

                  <div className="rounded border border-[var(--border)] bg-[var(--bg-canvas)] p-3 text-sm">
                    <h3 className="font-semibold">Automated Checker Verdict</h3>
                    <p className="mt-1 text-xs">
                      <strong>{autoCheck.verdict}</strong>
                      {autoCheck.coverageText ? ` · Coverage: ${autoCheck.coverageText}` : ''}
                      {autoCheck.providerModel ? ` · Checker: ${autoCheck.providerModel}` : ''}
                    </p>
                    <p className="mt-1 text-xs text-[var(--muted)]">{autoCheck.reason}</p>
                    {autoCheck.missedConcepts.length > 0 && (
                      <p className="mt-1 text-xs text-red-700">
                        Missed: {autoCheck.missedConcepts.join(', ')}
                      </p>
                    )}
                    {autoCheck.misconceptionHits.length > 0 && (
                      <p className="mt-1 text-xs text-red-700">
                        Misconception hits: {autoCheck.misconceptionHits.join(', ')}
                      </p>
                    )}
                  </div>

                  {canSubmitForReview(detail.status) && (
                    <div className="space-y-2 border-t border-[var(--border)] pt-4">
                      <h3 className="text-sm font-semibold">Submit for Human Review</h3>
                      <div className="flex flex-wrap gap-2">
                        <input
                          type="text"
                          value={submitReason}
                          onChange={(e) => setSubmitReason(e.target.value)}
                          placeholder="Optional submission note..."
                          className="flex-1 rounded border border-[var(--border)] bg-[var(--bg-canvas)] px-3 py-1.5 text-sm"
                        />
                        <button
                          type="button"
                          disabled={busy}
                          onClick={handleSubmitForReview}
                          className="rounded bg-[var(--ink)] px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50"
                        >
                          Submit for review
                        </button>
                      </div>
                    </div>
                  )}

                  {detail.status === 'in_review' && (
                    <div className="space-y-4 border-t border-[var(--border)] pt-4">
                      <h3 className="text-sm font-semibold">Reviewer Decision Checklist</h3>
                      <div className="grid gap-2 sm:grid-cols-2">
                        {REVIEW_CHECKLIST_ITEMS.map(({ key, label }) => (
                          <label key={key} className="flex items-start gap-2 text-xs">
                            <input
                              type="checkbox"
                              checked={Boolean(checklist[key])}
                              onChange={(e) =>
                                setChecklist((prev) => ({ ...prev, [key]: e.target.checked }))
                              }
                            />
                            <span>
                              <code>{key}</code> — {label}
                            </span>
                          </label>
                        ))}
                      </div>

                      <div className="flex flex-wrap items-center gap-3 text-sm">
                        <label htmlFor="blind-difficulty" className="font-medium">
                          Blind difficulty calibration:
                        </label>
                        <select
                          id="blind-difficulty"
                          value={difficulty}
                          onChange={(e) => setDifficulty(e.target.value)}
                          className="rounded border border-[var(--border)] bg-[var(--bg-canvas)] px-2.5 py-1.5 text-sm"
                        >
                          <option value="">Select difficulty...</option>
                          {DIFFICULTY_OPTIONS.map((opt) => (
                            <option key={opt} value={opt}>
                              {opt}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div className="space-y-1">
                        <label htmlFor="review-reason" className="block text-sm font-medium">
                          Review rationale (&gt;= 20 characters)
                        </label>
                        <textarea
                          id="review-reason"
                          rows={3}
                          value={reasons}
                          onChange={(e) => setReasons(e.target.value)}
                          placeholder="Explain why the question, reference answer, concepts, and checker alignment are ready or need fixes..."
                          className="w-full rounded border border-[var(--border)] bg-[var(--bg-canvas)] p-2.5 text-sm"
                        />
                      </div>

                      <div className="flex flex-wrap gap-3">
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => handleDecision(decisionChoices[0])}
                          className="rounded bg-emerald-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                        >
                          {decisionChoices[0] === 'adjudicate_approve' ? 'Adjudicate Approve' : 'Approve'}
                        </button>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => handleDecision(decisionChoices[1])}
                          className="rounded bg-red-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                        >
                          {decisionChoices[1] === 'adjudicate_reject' ? 'Adjudicate Reject' : 'Reject'}
                        </button>
                      </div>
                    </div>
                  )}
                </>
              )}
            </section>
          </div>
        )}
      </main>
    </div>
  );
}
