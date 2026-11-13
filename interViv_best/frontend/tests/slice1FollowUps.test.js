// Slice 1 (Checkpoint C): progress, banner, request button and report
// follow-up section, driven by REAL backend payloads
// (tests/helpers/emit_slice1_follow_up_payloads.py).
import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  PHASES,
  canRequestFollowUp,
  mandatoryProgress,
  progressPercent,
  restoreFromSession,
  roundFieldsFromPayload,
  systemFollowUpBanner,
} from '../src/lib/interviewLifecycle.js';
import { interviewStateFromSession } from '../src/lib/accountOverview.js';
import {
  buildReviewSummaryProps,
  followUpSectionRounds,
  mapRealDataToDashboard,
} from '../src/lib/dashboardMapping.js';

const testDir = path.dirname(fileURLToPath(import.meta.url));
const appRoot = path.resolve(testDir, '..', '..');
const localPython = path.join(appRoot, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const payloads = JSON.parse(execFileSync(
  existsSync(localPython) ? localPython : 'python3',
  [path.join(testDir, 'helpers', 'emit_slice1_follow_up_payloads.py')],
  {
    cwd: appRoot,
    encoding: 'utf8',
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' },
    stdio: ['ignore', 'pipe', 'pipe'],
    maxBuffer: 64 * 1024 * 1024,
  },
));
const LABEL = 'Follow-up (not scored)';

function view(state, phase) {
  return mandatoryProgress({
    mandatoryIndex: state.mandatoryIndex,
    mandatoryTotal: state.mandatoryTotal,
    mandatoryCompleted: state.mandatoryCompleted,
    round: state.round,
    totalRounds: state.totalRounds,
    phase,
    progressLabel: state.progressLabel,
  });
}

// What the page holds after each response (mirrors Interview.jsx setters).
function afterSubmit(resp) {
  return {
    mandatoryIndex: resp.current_mandatory_index,
    mandatoryTotal: resp.mandatory_total,
    mandatoryCompleted: resp.mandatory_completed,
    round: null,
    totalRounds: resp.total_rounds,
    progressLabel: resp.progress_label || null,
  };
}
function afterOpen(resp) {
  const fields = roundFieldsFromPayload(resp.active_round);
  return {
    mandatoryIndex: fields.mandatoryIndex,
    mandatoryTotal: resp.mandatory_total,
    mandatoryCompleted: resp.mandatory_completed,
    round: fields.round,
    totalRounds: resp.total_rounds,
    followUpLabel: fields.followUpLabel,
    progressLabel: fields.progressLabel,
  };
}

test('progress: parent 3/10, follow-up 3/10, next mandatory 4/10; follow-up never advances it', () => {
  const steps = [
    ['parent review', view(afterSubmit(payloads.parent_submit), PHASES.REVIEWING)],
    ['follow-up answering', view(afterOpen(payloads.follow_up_activate), PHASES.ANSWERING)],
    ['follow-up review', view(afterSubmit(payloads.follow_up_submit), PHASES.REVIEWING)],
    ['next answering', view(afterOpen(payloads.next_activate), PHASES.ANSWERING)],
    ['next review', view(afterSubmit(payloads.next_submit), PHASES.REVIEWING)],
  ];
  assert.deepEqual(steps.map(([, v]) => v.label), ['3/10', '3/10', '3/10', '4/10', '4/10']);
  assert.deepEqual(steps.map(([, v]) => v.percent), [30, 30, 30, 30, 40]);
  assert.ok(steps.every(([, v]) => v.mandatory));
});

test('progress survives refresh and /continue at every point', () => {
  const refreshed = [
    ['refresh_parent_review', PHASES.REVIEWING, '3/10', 30],
    ['refresh_follow_up_answering', PHASES.ANSWERING, '3/10', 30],
    ['refresh_follow_up_review', PHASES.REVIEWING, '3/10', 30],
    ['refresh_next_answering', PHASES.ANSWERING, '4/10', 30],
  ];
  for (const [name, phase, label, percent] of refreshed) {
    const state = interviewStateFromSession(payloads[name]);
    assert.equal(state.phase, phase, name);
    const v = view({ ...state, round: state.round, totalRounds: state.totalRounds }, state.phase);
    assert.deepEqual([v.label, v.percent], [label, percent], name);
  }
  const reopened = afterOpen(payloads.follow_up_continue);
  assert.deepEqual([view(reopened, PHASES.ANSWERING).label, reopened.followUpLabel], ['3/10', LABEL]);
});

test('system banner during answering and review, from the server label only', () => {
  const answering = interviewStateFromSession(payloads.refresh_follow_up_answering);
  const review = interviewStateFromSession(payloads.refresh_follow_up_review);
  assert.equal(answering.followUpLabel, LABEL);
  assert.equal(review.followUpLabel, LABEL);
  assert.equal(payloads.follow_up_submit.follow_up_label, LABEL);
  assert.equal(systemFollowUpBanner(LABEL).title, LABEL);
  assert.match(systemFollowUpBanner(LABEL).body, /not scored/);
  // Mandatory rounds and candidate follow-ups carry no server label: no banner.
  assert.equal(interviewStateFromSession(payloads.refresh_next_answering).followUpLabel, null);
  assert.equal(systemFollowUpBanner(null), null);
});

test("parent's request button is hidden once its system follow-up exists, also after refresh", () => {
  const base = { roundType: 'technical_short_answer', phase: PHASES.REVIEWING, followUpNote: '' };
  assert.equal(payloads.parent_submit.system_follow_up_scheduled, true);
  assert.equal(canRequestFollowUp({ ...base, systemFollowUpScheduled: payloads.parent_submit.system_follow_up_scheduled }), false);
  const restored = interviewStateFromSession(payloads.refresh_parent_review);
  assert.equal(restored.systemFollowUpScheduled, true);
  assert.equal(canRequestFollowUp({ ...base, systemFollowUpScheduled: restored.systemFollowUpScheduled }), false);
  // Earlier rounds (no system follow-up) keep the button.
  const earlier = payloads.refresh_parent_review.round_history.find((e) => e.round === 2);
  assert.equal(earlier.system_follow_up_scheduled, false);
  assert.equal(canRequestFollowUp({ ...base, systemFollowUpScheduled: false }), true);
  assert.equal(canRequestFollowUp({ ...base, phase: PHASES.ANSWERING, systemFollowUpScheduled: false }), false);
});

test('candidate-requested follow-up: labelled "Optional follow-up", mandatory progress stays at 100%', () => {
  const flow = payloads.candidate_follow_up;
  const OPTIONAL = 'Optional follow-up';
  const steps = [
    ['last mandatory review', view(afterSubmit(flow.last_mandatory_submit), PHASES.REVIEWING)],
    ['follow-up answering', view(afterOpen(flow.follow_up_activate), PHASES.ANSWERING)],
    ['follow-up reopened', view(afterOpen(flow.follow_up_continue), PHASES.ANSWERING)],
    ['follow-up review', view(afterSubmit(flow.follow_up_submit), PHASES.REVIEWING)],
  ];
  assert.deepEqual(steps.map(([, v]) => v.label), ['2/2', OPTIONAL, OPTIONAL, OPTIONAL]);
  assert.deepEqual(steps.map(([, v]) => v.percent), [100, 100, 100, 100]);
  assert.deepEqual(steps.map(([, v]) => v.optional), [false, true, true, true]);
  // After a refresh: while answering, and once it is submitted (it is the
  // last round, so the session is then complete).
  for (const [name, phase] of [['refresh_follow_up_answering', PHASES.ANSWERING], ['refresh_follow_up_review', PHASES.COMPLETED]]) {
    const state = interviewStateFromSession(flow[name]);
    assert.deepEqual([state.phase, state.progressLabel], [phase, OPTIONAL], name);
    const v = view(state, state.phase);
    assert.deepEqual([v.label, v.percent, v.optional], [OPTIONAL, 100, true], name);
    // Not a system follow-up: no server label, so no system banner.
    assert.equal(state.followUpLabel, null, name);
    assert.equal(systemFollowUpBanner(state.followUpLabel), null, name);
  }
  // Its existing eligibility facts are untouched (the page still shows
  // "Follow-up · Practiced with help" from these).
  assert.deepEqual(
    [flow.follow_up_submit.is_follow_up, flow.follow_up_submit.assessment_eligibility, flow.follow_up_submit.follow_up_label],
    [true, 'excluded', undefined],
  );
  // Mandatory rounds and system follow-ups never carry the label.
  assert.equal(flow.last_mandatory_submit.progress_label, undefined);
  assert.equal(payloads.follow_up_activate.active_round.progress_label, undefined);
  assert.equal(payloads.follow_up_submit.progress_label, undefined);
  // Index-less plan or older server: the label still applies and the bar is full.
  const legacy = mandatoryProgress({ round: 5, totalRounds: 5, phase: PHASES.ANSWERING, progressLabel: OPTIONAL });
  assert.deepEqual([legacy.label, legacy.percent, legacy.optional, legacy.mandatory], [OPTIONAL, 100, true, false]);
});

test('legacy payloads (no mandatory fields) keep the historical progress exactly', () => {
  for (const [round, totalRounds, phase] of [[1, 5, PHASES.ANSWERING], [3, 5, PHASES.REVIEWING], [5, 5, PHASES.COMPLETED]]) {
    const v = mandatoryProgress({ round, totalRounds, phase });
    assert.equal(v.mandatory, false);
    assert.equal(v.label, `${round}/${totalRounds}`);
    assert.equal(v.percent, progressPercent({ round, totalRounds, phase }));
  }
  const legacy = restoreFromSession({ status: 'active', active_round: { round: 2, status: 'in_progress', question: 'Q?' } });
  assert.equal(legacy.current.mandatoryIndex, null);
});

test('report: system follow-up (even with a numeric score) leaves every assessed view', () => {
  const session = payloads.system_report_forced_score;
  const followUps = followUpSectionRounds(session);
  assert.deepEqual(followUps.map((r) => [r.round, r.final_score]), [[4, 95]]);
  const mapped = mapRealDataToDashboard(session);
  assert.deepEqual(mapped.followUps.map((f) => [f.round, f.label, f.parentRound]), [[4, LABEL, 3]]);
  assert.equal(mapped.rounds.length, 10);                       // scored timeline
  assert.ok(mapped.rounds.every((r) => r.question !== followUps[0].question));
  assert.equal(mapped.performance.score.length, 10);            // score chart
  assert.ok(!mapped.performance.score.some((p) => p.value === 95));
  assert.equal(mapped.session.durationLabel, '10 of 10 rounds scored');
  const summary = mapped.reviewSummary;                          // assessed summary
  assert.equal(summary.completedRounds, 10);
  assert.equal(summary.totalRounds, 10);
  assert.ok(!summary.unscored.some((u) => u.round === 4));
  assert.ok(!mapped.feedbackCards.find((c) => c.id === 'c4').body.includes('95'));
});

test("today's presentation of a reviewed scored candidate follow-up is pinned (chart, best, range, count)", () => {
  // Same values from the pre-Slice-1 payload (captured on 9c9b5f2, no
  // report_section field) and from the current server.
  const pre = JSON.parse(readFileSync(path.join(appRoot, 'tests/fixtures/slice1_account_transcript.json'), 'utf8'))
    .steps.find((s) => s.step === 's1_report').body;
  const now = payloads.reviewed_candidate_report;
  assert.ok(now.rounds.every((r) => r.report_section === 'rounds'));
  assert.ok(pre.rounds.every((r) => !('report_section' in r)));
  for (const [name, session] of [['pre-change', pre], ['current', now]]) {
    const mapped = mapRealDataToDashboard(session);
    const summary = buildReviewSummaryProps(session, mapped);
    assert.deepEqual(mapped.performance.score.map((p) => p.value), [80, 60, 100], name);      // chart
    assert.match(mapped.feedbackCards.find((c) => c.id === 'c4').body, /best round scored 100%/, name);
    assert.equal(summary.scoreRange, 40, name);                                                 // range
    assert.equal(mapped.session.durationLabel, '3 of 3 rounds scored', name);                   // count
    assert.deepEqual([summary.completedRounds, summary.totalRounds], [3, 3], name);
    assert.equal(session.averages.final_score, 70, name);                                       // assessed mean
    // Two measured blocks (DBMS, OS): today the overall is "Mixed session" with no single score.
    assert.deepEqual([mapped.blended, mapped.overall.score], [true, null], name);
    assert.deepEqual(mapped.followUps, [], name);
  }
});

test('the follow-up section comes only from the server field, never inferred', () => {
  const session = structuredClone(payloads.system_report_forced_score);
  const followUp = session.rounds.find((r) => r.round === 4);
  // The report still exposes legacy hints (is_follow_up, follow_up_scoring,
  // eligibility reasons); without report_section none of them is used.
  assert.equal(followUp.is_follow_up, true);
  for (const r of session.rounds) delete r.report_section;
  const mapped = mapRealDataToDashboard(session);
  assert.deepEqual(mapped.followUps, []);
  assert.equal(mapped.rounds.length, 11);
});
