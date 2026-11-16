import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';
import {
  createStagedSessionController, interviewScreenForSession,
  quickInterviewPayload, stagedSessionState, startQuickInterview,
} from '../src/lib/stagedSession.js';
import { mapFullInterviewToStartPayload } from '../src/lib/practiceBuilder.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const turn = (round = 1, stage = 'core') => ({ round, stage, status: 'in_progress',
  round_type: 'technical_short_answer', question: 'Explain a generator.', skill: 'Python',
  started_at: '2026-11-16T10:00:00Z', expires_at: '2026-11-16T10:02:00Z' });
const session = (extra = {}) => ({ session_id: 'quick-1', flow_version: 'staged_v1', preset: 'quick',
  status: 'active', total_rounds: 3, active_round: turn(), round_history: [], pending_round: null, ...extra });
const ready = () => session({ active_round: null,
  round_history: [{ ...turn(), status: 'submitted', final_score: null }],
  pending_round: { ...turn(2), status: 'ready', question: undefined } });
const clone = value => structuredClone(value);

test('Quick sends only staged preset fields; assessment suppresses optional follow-ups', () => {
  assert.deepEqual(quickInterviewPayload({ skills: [' Python ', 'Python'], candidateId: 'candidate',
    targetRoleId: 'role', targetCompanyId: 'company', allowOptionalFollowUps: true }), {
    flow_version: 'staged_v1', preset: 'quick', skills: ['Python'], candidate_id: 'candidate',
    target_role_id: 'role', target_company_id: 'company', practice_mode: 'coached_practice', allow_optional_follow_ups: true,
  });
  assert.equal(quickInterviewPayload({ skills: ['Python'], practiceMode: 'assessment', allowOptionalFollowUps: true }).allow_optional_follow_ups, false);
  assert.throws(() => quickInterviewPayload({ skills: [] }), /Select at least one skill/);
  const legacy = mapFullInterviewToStartPayload({ skills: ['Python'], roundsPerSkill: 2 }).payload;
  assert.equal(legacy.rounds_per_skill, 2);
  assert.equal(legacy.flow_version, undefined);
});

test('Quick probes the exact start payload before creating a session', async () => {
  const calls = [];
  const started = await startQuickInterview({ skills: ['Python'] }, {
    fetchAvailability: async payload => { calls.push(['probe', clone(payload)]); return { available: true }; },
    startSession: async payload => { calls.push(['start', clone(payload)]); return { session_id: 'created' }; },
  });
  assert.equal(started.session_id, 'created');
  assert.deepEqual(calls.map(c => c[0]), ['probe', 'start']);
  assert.deepEqual(calls[0][1], calls[1][1]);
});

test('unavailable content and failed probes never start or silently fall through', async () => {
  let starts = 0;
  await assert.rejects(startQuickInterview({ skills: ['Python'] }, {
    fetchAvailability: async () => ({ available: false, blocks: [{ available: false, reason: 'No reviewed bundles available.' }] }),
    startSession: async () => { starts++; },
  }), error => error.status === 422 && /No reviewed bundles/.test(error.message));
  await assert.rejects(startQuickInterview({ skills: ['Python'] }, {
    fetchAvailability: async () => { throw new Error('Probe interrupted'); },
    startSession: async () => { starts++; },
  }), /Probe interrupted/);
  assert.equal(starts, 0);
});

test('staged completion stays on the new screen; legacy routing stays unchanged', () => {
  assert.equal(interviewScreenForSession(session({ status: 'completed' })), 'staged');
  assert.equal(interviewScreenForSession({ status: 'completed' }), 'dashboard');
  assert.equal(interviewScreenForSession({ status: 'active' }), 'legacy');
});

test('server resume retains deadlines and counts submitted null-score rounds without evaluations', () => {
  const raw = session({ active_round: { ...turn(3, 'follow_up'), is_follow_up: true, follow_up_parent_round: 2,
    final_score: 99, feedback: { content: ['LEAK'] }, scoring_breakdown: { secret: 'LEAK' } },
  total_rounds: 4, round_history: [{ ...turn(1), status: 'submitted', final_score: null }, { ...turn(2), status: 'submitted', final_score: null }] });
  const state = stagedSessionState(raw);
  assert.equal(state.phase, 'answering');
  assert.equal(state.answeredCount, 2);
  assert.equal(state.totalRounds, 4);
  assert.equal(state.active.expiresAt, raw.active_round.expires_at);
  assert.equal(state.active.parentRound, 2);
  assert.doesNotMatch(JSON.stringify(state), /LEAK|final_score|scoring_breakdown/);
  assert.equal(stagedSessionState(ready()).phase, 'ready');
  assert.equal(stagedSessionState(session({ status: 'content_blocked' })).phase, 'blocked');
  assert.equal(stagedSessionState(session({ status: 'completed' })).phase, 'completed');
});

test('real offline backend Quick journey resumes every turn, including inline follow-up, with no feedback call', async () => {
  const appRoot = path.resolve(root, '..');
  const fixtures = JSON.parse(execFileSync(path.join(appRoot, '.venv/bin/python'),
    [path.join(root, 'tests/helpers/emit_staged_quick_payloads.py')], {
      cwd: appRoot, encoding: 'utf8', env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' }, maxBuffer: 16 * 1024 * 1024,
    }));
  const calls = [];
  let index = 0;
  const api = {
    fetchSession: async () => { calls.push('GET session'); return clone(fixtures.states[++index]); },
    submitAnswer: async payload => {
      const operation = fixtures.operations[index];
      assert.equal(operation.kind, 'submitAnswer'); assert.equal(payload.round, operation.round);
      calls.push('POST answer'); return { ...operation.response, feedback: { content: ['LEAK'] }, final_score: 99 };
    },
    activateRound: async (id, rn) => {
      const operation = fixtures.operations[index];
      assert.equal(operation.kind, 'activateRound'); assert.equal(rn, operation.round);
      calls.push('POST activate'); return operation.response;
    },
    fetchRoundFeedback: async () => { throw new Error('Forbidden feedback request'); },
  };
  const controller = createStagedSessionController({ session: fixtures.states[0], api });
  for (const operation of fixtures.operations) {
    assert.equal(operation.kind === 'submitAnswer' ? await controller.submit('Candidate answer') : await controller.advance(), true);
    const expected = stagedSessionState(fixtures.states[index]);
    assert.deepEqual(controller.snapshot(), expected);
    assert.doesNotMatch(JSON.stringify(controller.snapshot()), /LEAK|final_score|scoring_breakdown/);
  }
  assert.equal(controller.snapshot().phase, 'completed');
  assert.equal(controller.snapshot().answeredCount, fixtures.states.at(-1).round_history.length);
  assert.equal(calls.filter(c => c === 'POST answer').length, fixtures.states.at(-1).round_history.length);
});

test('duplicate submits and premature activation cannot issue another mutation', async () => {
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  let posts = 0;
  const controller = createStagedSessionController({ session: session(), api: {
    submitAnswer: async () => { posts++; await gate; }, fetchSession: async () => ready(),
  } });
  assert.equal(await controller.advance(), false);
  const pending = controller.submit('An answer');
  assert.equal(await controller.submit('Duplicate'), false);
  release(); await pending;
  assert.equal(posts, 1);
});

test('lost submission response reconciles accepted answer before enabling another POST', async () => {
  let posts = 0;
  const controller = createStagedSessionController({ session: session(), api: {
    submitAnswer: async () => { posts++; throw new Error('Response lost'); }, fetchSession: async () => ready(),
  } });
  assert.equal(await controller.submit('Saved answer'), false);
  assert.equal(controller.snapshot().phase, 'ready');
  assert.equal(controller.snapshot().needsRefresh, false);
  assert.equal(await controller.submit('Duplicate'), false);
  assert.equal(posts, 1);
});

test('failed reconciliation locks mutations until explicit refresh succeeds', async () => {
  let available = false;
  let posts = 0;
  const controller = createStagedSessionController({ session: session(), api: {
    submitAnswer: async () => { posts++; },
    fetchSession: async () => { if (!available) throw new Error('Offline'); return ready(); },
  } });
  await controller.submit('Candidate answer');
  assert.equal(controller.snapshot().needsRefresh, true);
  assert.equal(await controller.submit('Do not repeat'), false);
  available = true;
  assert.equal(await controller.refresh(), true);
  assert.equal(controller.snapshot().phase, 'ready');
  assert.equal(posts, 1);
});

test('activation retry retains a prepared round and its original server deadline', async () => {
  let attempts = 0;
  const opened = session({ active_round: turn(2), round_history: ready().round_history });
  const controller = createStagedSessionController({ session: ready(), api: {
    activateRound: async () => { if (++attempts === 1) throw new Error('Activation interrupted'); },
    fetchSession: async () => attempts === 1 ? ready() : opened,
  } });
  await controller.advance();
  assert.equal(controller.snapshot().phase, 'ready');
  assert.equal(await controller.advance(), true);
  assert.equal(controller.snapshot().active.expiresAt, opened.active_round.expires_at);
});

test('content-blocked continuation refetches state without evaluating the saved answer', async () => {
  const calls = [];
  const controller = createStagedSessionController({ session: session({ status: 'content_blocked', active_round: null,
    round_history: ready().round_history, progression_blocked_reason: 'No matching content available.' }), api: {
    continueSession: async () => { calls.push('continue'); return { final_score: 99 }; },
    fetchSession: async () => { calls.push('fetch'); return ready(); },
  } });
  assert.equal(await controller.retryBlocked(), true);
  assert.deepEqual(calls, ['continue', 'fetch']);
  assert.equal(controller.snapshot().phase, 'ready');
});

test('late responses after disposal cannot publish into another session', async () => {
  let release;
  const response = new Promise(resolve => { release = resolve; });
  const changes = [];
  const controller = createStagedSessionController({ session: session(), onChange: value => changes.push(value), api: {
    fetchSession: async () => response,
  } });
  const refresh = controller.refresh();
  controller.dispose();
  release(ready());
  assert.equal(await refresh, false);
  assert.equal(changes.length, 1); // loading update only, before navigation
});

test('drafts use the real nested response contract and are scoped to the active round', async () => {
  const saved = [];
  const controller = createStagedSessionController({ session: session(), api: {
    fetchAnswerDraft: async () => ({ draft: { answer_text: 'Restored answer' } }),
    saveAnswerDraft: async (id, payload) => saved.push([id, payload]),
  } });
  assert.equal(await controller.readDraft(1), 'Restored answer');
  assert.equal(await controller.saveDraft(2, 'Wrong round'), false);
  assert.equal(await controller.saveDraft(1, 'Edited answer'), true);
  assert.deepEqual(saved, [['quick-1', { round: 1, answer_text: 'Edited answer' }]]);
  controller.dispose();
  assert.equal(await controller.readDraft(1), null);
});

test('a missing draft is a normal empty answer, while draft service failures stay visible', async () => {
  let status = 404;
  const controller = createStagedSessionController({ session: session(), api: {
    fetchAnswerDraft: async () => { const error = new Error('Draft request failed'); error.status = status; throw error; },
  } });
  assert.equal(await controller.readDraft(1), '');
  status = 503;
  await assert.rejects(controller.readDraft(1), /Draft request failed/);
});

const bundled = await build({ stdin: { resolveDir: root, loader: 'jsx', contents: `
  import React from 'react';
  import { renderToStaticMarkup } from 'react-dom/server';
  import { MemoryRouter } from 'react-router-dom';
  import StagedInterview from './src/pages/StagedInterview.jsx';
  import StagedLauncherCard from './src/components/staged/StagedLauncherCard.jsx';
  export const render = session => renderToStaticMarkup(<MemoryRouter><StagedInterview session={session} /></MemoryRouter>);
  export const launcher = busy => renderToStaticMarkup(<StagedLauncherCard busy={busy} onStart={() => {}} />);
` }, bundle: true, platform: 'node', format: 'cjs', write: false, logLevel: 'silent',
  define: { 'process.env.NODE_ENV': '"production"' } });
const module = { exports: {} };
new Function('require', 'module', 'exports', bundled.outputFiles[0].text)(createRequire(path.join(root, 'package.json')), module, module.exports);
const { render, launcher } = module.exports;

test('new screen renders prompts, follow-up identity and completion link without result leakage', () => {
  const active = render(session({ active_round: { ...turn(3, 'follow_up'), follow_up_parent_round: 2,
    feedback: 'LEAK', final_score: 99, scoring_breakdown: { text: 'LEAK' } } }));
  assert.match(active, /Explain a generator/);
  assert.match(active, /Follow-up to question 2/);
  assert.doesNotMatch(active, /LEAK|99%|Evaluation Score/);
  const complete = render(session({ status: 'completed', final_score: 99, feedback: 'LEAK' }));
  assert.match(complete, /Interview complete/);
  assert.match(complete, /href="\/dashboard\/quick-1"/);
  assert.doesNotMatch(complete, /LEAK|99%|Submit answer/);
});

test('ready and blocked screens preserve receipts without revealing pending prompts', () => {
  assert.match(render(ready()), /Answer saved/);
  assert.doesNotMatch(render(ready()), /Explain a generator/);
  assert.match(render(session({ status: 'content_blocked', progression_blocked_reason: 'No matching content available.' })), /No matching content available/);
  assert.match(render(session({ status: 'content_blocked' })), /Retry continuation/);
});

test('Quick launcher exposes one actionable preset and a busy state', () => {
  assert.match(launcher(false), /Start Quick interview/);
  assert.doesNotMatch(launcher(false), /Start Full/);
  assert.match(launcher(true), /disabled=""/);
});
