import assert from 'node:assert/strict';
import test from 'node:test';
import { safeNext, authDestination } from '../src/lib/authRedirect.js';
import { displayScore, interviewStateFromSession } from '../src/lib/accountOverview.js';

const origin = 'http://127.0.0.1:5173';
test('auth returns to supported static and dynamic destinations after normalization', () => {
  for (const path of ['/home', '/practice?mode=custom', '/jobs?q=SQL&where=Pune', '/resources?skill_id=DBMS', '/interview/abc-123', '/dashboard/abc-123', '/gap-analysis/me/tcs_swe', '/roadmap/u-123/tcs_swe?days=14']) assert.equal(safeNext(path, origin), path);
  assert.equal(safeNext('/practice/../home', origin), '/home');
  assert.equal(safeNext('/%70ractice?mode=full', origin), '/practice?mode=full');
});
test('auth rejects external destinations, escaped separators, loops and unsupported paths', () => {
  for (const path of [null, {}, '', 'https://evil.test', '//evil.test', '/\\evil.test', '/%5cevil.test', '/%2f%2fevil.test', '/%255cevil.test', '/interview/a%2Fb', '/interview/%252e%252e', '/login', '/signup', '/register', '/practice/../login', '/%6cogin?next=/login', '/unknown', '/problems', '/home\n', ' /home', 'javascript:alert(1)']) assert.equal(safeNext(path, origin), '/home', String(path));
});
test('query destinations and login/signup state use the same safe rules', () => {
  assert.equal(authDestination({ search: '?next=%2Fjobs%3Fq%3DPython' }, origin), '/jobs?q=Python');
  assert.equal(authDestination({ state: { next: '//evil.test' }, search: '?next=/practice' }, origin), '/home');
  assert.equal(authDestination({ state: { next: '/dashboard/owned-id' } }, origin), '/dashboard/owned-id');
  assert.equal(authDestination({}, origin), '/home');
});
test('real zeros remain visible while missing values are unmeasured', () => {
  assert.equal(displayScore(0), '0%');
  for (const value of [null, undefined, NaN, '', '0']) assert.equal(displayScore(value), 'Not measured');
});
test('resume restores only server-supplied session identity, round, options and deadline', () => {
  const questions = [{ id: 'q1', options: [{ id: 'b' }, { id: 'a' }] }];
  const session = { session_id: 'owned', candidate_id: 'candidate', current_skill: 'DBMS', total_rounds: 3, last_round: 2, active_round: { round: 2, round_type: 'mcq', question_context: { questions }, config_json: { count: 1 }, expires_at: '2026-09-07T00:20:00Z', elo_before: 0 } };
  const state = interviewStateFromSession(session);
  assert.equal(state.sessionId, 'owned');
  assert.equal(state.round, 2);
  assert.equal(state.totalRounds, 3);
  assert.equal(state.elo, 0);
  assert.deepEqual(state.question_context.questions, questions);
  assert.equal(state.expires_at, session.active_round.expires_at);
  assert.throws(() => interviewStateFromSession({ session_id: 'no-round' }));
});
