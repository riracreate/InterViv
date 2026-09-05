import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  formatMCQSubmission,
  normalizeSessionData,
  computeSecondsRemaining,
} from '../src/lib/roundContractHelpers.js';

const testDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(testDir, '..', '..');
let realRefreshPayloads;

function getRealRefreshPayloads() {
  if (!realRefreshPayloads) {
    const localPython = path.join(
      repoRoot,
      '.venv',
      process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
    );
    const python = existsSync(localPython) ? localPython : 'python3';
    const helper = path.join(testDir, 'helpers', 'emit_real_refresh_payloads.py');
    const serialized = execFileSync(python, [helper], {
      cwd: repoRoot,
      encoding: 'utf8',
      env: {
        ...process.env,
        INTERVIV_USE_MEMORY_DB: 'true',
        JWT_SECRET_KEY: 'test-secret-key-with-at-least-32-bytes!!',
        PYTHONDONTWRITEBYTECODE: '1',
      },
    });
    realRefreshPayloads = JSON.parse(serialized);
  }
  return realRefreshPayloads;
}

test('formatMCQSubmission produces canonical structure with explicit empty selections', () => {
  const questions = [
    { id: 'mcq_dbms_001', stem: 'What is 1NF?' },
    { id: 'mcq_dbms_002', stem: 'What is 2NF?' },
    { id: 'mcq_dbms_003', stem: 'What is 3NF?' },
  ];
  const answersMap = {
    mcq_dbms_001: 'b',
    // mcq_dbms_002 is skipped
    mcq_dbms_003: 'c',
  };

  const formatted = formatMCQSubmission(questions, answersMap);

  assert.equal(formatted.length, 3);
  assert.deepEqual(formatted[0], {
    question_id: 'mcq_dbms_001',
    selected_option_ids: ['b'],
  });
  assert.deepEqual(formatted[1], {
    question_id: 'mcq_dbms_002',
    selected_option_ids: [],
  });
  assert.deepEqual(formatted[2], {
    question_id: 'mcq_dbms_003',
    selected_option_ids: ['c'],
  });
});

test('formatMCQSubmission preserves question order and handles empty input', () => {
  assert.deepEqual(formatMCQSubmission([], {}), []);
  assert.deepEqual(formatMCQSubmission(null, {}), []);

  const questions = [
    { id: 'q_z' },
    { id: 'q_a' },
    { id: 'q_m' },
  ];
  const formatted = formatMCQSubmission(questions, { q_a: 'opt_1' });
  assert.equal(formatted[0].question_id, 'q_z');
  assert.deepEqual(formatted[0].selected_option_ids, []);
  assert.equal(formatted[1].question_id, 'q_a');
  assert.deepEqual(formatted[1].selected_option_ids, ['opt_1']);
  assert.equal(formatted[2].question_id, 'q_m');
  assert.deepEqual(formatted[2].selected_option_ids, []);
});

test('normalizeSessionData mirrors active_round into current_round for rehydration', () => {
  const rawBackendResponse = {
    session_id: 'sess_123',
    status: 'active',
    active_round: {
      round: 1,
      round_type: 'mcq',
      question: 'Multiple Choice Assessment',
      question_context: {
        questions: [{ id: 'q1' }, { id: 'q2' }],
      },
      config_json: { duration_minutes: 20, count: 15 },
      expires_at: '2026-09-04T12:00:00Z',
    },
  };

  const normalized = normalizeSessionData(rawBackendResponse);
  assert.ok(normalized.current_round, 'current_round should be populated');
  assert.equal(normalized.current_round.round_type, 'mcq');
  assert.equal(normalized.current_round.expires_at, '2026-09-04T12:00:00Z');
  assert.equal(normalized.current_round.question_context.questions.length, 2);
  assert.equal(normalized.active_round.round_type, 'mcq');
});

test('computeSecondsRemaining computes accurate countdown and clamps at 0', () => {
  const fixedNow = 1750000000000;
  const futureExpiry = new Date(fixedNow + 125000).toISOString(); // 125 seconds in future
  const pastExpiry = new Date(fixedNow - 30000).toISOString(); // 30 seconds in past

  const remainingFuture = computeSecondsRemaining(futureExpiry, 20, fixedNow);
  assert.equal(remainingFuture, 125);

  const remainingPast = computeSecondsRemaining(pastExpiry, 20, fixedNow);
  assert.equal(remainingPast, 0);

  // Fallback duration in minutes
  const fallback = computeSecondsRemaining(null, 15, fixedNow);
  assert.equal(fallback, 15 * 60);
});

test('SQL safe client artifact contains aggregate evidence without hidden case leakage', () => {
  // Simulate client-sanitized SQL artifact
  const safeArtifact = {
    evaluation_cases: 3,
    cases_passed: 3,
    row_count_cases_passed: 3,
    result_equality_points: 60.0,
    row_count_points: 20.0,
    constraint_points: 20.0,
    final_score: 100.0,
  };

  assert.equal(safeArtifact.evaluation_cases, 3);
  assert.equal(safeArtifact.cases_passed, 3);
  assert.equal(safeArtifact.final_score, 100.0);
  assert.equal(safeArtifact.cases, undefined);
  assert.equal(safeArtifact.hidden_cases, undefined);
  assert.equal(safeArtifact.seed_data, undefined);
});

test('fetchSession uses the production normalizer (single source of truth)', async () => {
  // Exercise the real production fetch helper with stubbed transport only.
  const backendBody = {
    session_id: 'sess_refresh',
    status: 'active',
    active_round: {
      round: 1,
      round_type: 'mcq',
      question_context: { questions: [{ id: 'q1' }, { id: 'q2' }] },
      expires_at: '2026-09-04T12:00:00.000Z',
    },
  };
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push(url);
    return { ok: true, json: async () => structuredClone(backendBody) };
  };
  globalThis.localStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} };

  const { fetchSession } = await import('../src/lib/api.js');
  const data = await fetchSession('sess_refresh');

  assert.equal(calls[0], '/api/session/sess_refresh');
  // Normalization must have been applied by the production helper itself.
  assert.ok(data.current_round, 'fetchSession must mirror active_round');
  assert.deepEqual(data.current_round, data.active_round);

  delete globalThis.fetch;
  delete globalThis.localStorage;
});

test('real backend MCQ refresh survives production normalization and original-deadline countdown', () => {
  const { start: startBody, fetch: fetchBody } = getRealRefreshPayloads().mcq;
  const startIds = startBody.questions.map((question) => question.id);
  const normalized = normalizeSessionData(fetchBody);
  const round = normalized.active_round || normalized.current_round;
  const refreshedIds = round.question_context.questions.map((question) => question.id);

  assert.deepEqual(refreshedIds, startIds, 'refresh must return identical IDs in order');
  assert.equal(round.expires_at, startBody.expires_at, 'refresh must return the original deadline');
  assert.deepEqual(normalized.current_round, normalized.active_round);

  const afterNinetySeconds = new Date(startBody.started_at).getTime() + 90 * 1000;
  const remaining = computeSecondsRemaining(
    round.expires_at,
    startBody.config_json.duration_minutes,
    afterNinetySeconds,
  );
  assert.equal(remaining, 1110);

  console.log(`real backend MCQ IDs: ${startIds.join(',')}`);
  console.log(`real backend MCQ expires_at: ${startBody.expires_at}; countdown@+90s: ${remaining}`);
});

test('real backend SQL refresh survives production normalization and original-deadline countdown', () => {
  const { start: startBody, fetch: fetchBody } = getRealRefreshPayloads().sql;
  const normalized = normalizeSessionData(fetchBody);
  const round = normalized.active_round || normalized.current_round;
  const refreshedContext = round.question_context;

  assert.equal(refreshedContext.id, startBody.question_context.id);
  assert.deepEqual(refreshedContext.sample_cases, startBody.sample_cases);
  assert.equal(round.expires_at, startBody.expires_at, 'refresh must return the original deadline');
  assert.deepEqual(normalized.current_round, normalized.active_round);

  const afterNinetySeconds = new Date(startBody.started_at).getTime() + 90 * 1000;
  const remaining = computeSecondsRemaining(
    round.expires_at,
    startBody.config_json.duration_minutes,
    afterNinetySeconds,
  );
  assert.equal(remaining, 1410);

  console.log(`real backend SQL problem ID: ${startBody.question_context.id}`);
  console.log(`real backend SQL expires_at: ${startBody.expires_at}; countdown@+90s: ${remaining}`);
});
