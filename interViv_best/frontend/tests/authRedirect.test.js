import assert from 'node:assert/strict';
import test from 'node:test';
import { safeNext, authDestination, loginHref } from '../src/lib/authRedirect.js';
import { displayScore, interviewStateFromSession } from '../src/lib/accountOverview.js';

const origin = 'http://127.0.0.1:5173';
test('auth returns to supported static and dynamic destinations after normalization', () => {
  for (const path of ['/home', '/practice?mode=custom', '/problems', '/learn', '/jobs?q=SQL&where=Pune', '/resources?skill_id=DBMS', '/interview/abc-123', '/dashboard/abc-123', '/gap-analysis/me/tcs_swe', '/roadmap/u-123/tcs_swe?days=14']) assert.equal(safeNext(path, origin), path);
  assert.equal(safeNext('/practice/../home', origin), '/home');
  assert.equal(safeNext('/%70ractice?mode=full', origin), '/practice?mode=full');
});
test('auth rejects external destinations, escaped separators, loops and unsupported paths', () => {
  for (const path of [null, {}, '', 'https://evil.test', 'https://example.com', 'http://example.com', '//evil.test', '/\\', '/\\evil.test', '/%5cevil.test', '/%2f%2fevil.test', '/%255cevil.test', '/interview/a%2Fb', '/interview/%252e%252e', '/login', '/signup', '/register', '/practice/../login', '/%6cogin?next=/login', '/unknown', '/home\n', ' /home', 'javascript:alert(1)']) assert.equal(safeNext(path, origin), '/home', String(path));
  assert.equal(loginHref('/upload?step=1#resume', origin), '/login?next=%2Fupload%3Fstep%3D1%23resume');
  assert.equal(loginHref('https://example.com', origin), '/login?next=%2Fhome');
  assert.equal(loginHref('//evil.test', origin), '/login?next=%2Fhome');
  assert.equal(loginHref('/\\evil.test', origin), '/login?next=%2Fhome');
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
  assert.equal(state.progressionBlocked, false);
  assert.throws(() => interviewStateFromSession({ session_id: 'no-round' }));
});

test('content_blocked resume carries score feedback and retry flags', () => {
  const session = {
    session_id: 'blocked',
    candidate_id: 'candidate',
    status: 'content_blocked',
    progression_blocked_reason: 'No matching inventory.',
    current_skill: 'DBMS',
    total_rounds: 2,
    last_round: 1,
    active_round: {
      round: 1,
      round_type: 'technical_short_answer',
      question: 'What is ACID?',
      final_score: 70,
      feedback: { next_step: 'Review atomicity' },
      elo_before: 1200,
    },
  };
  const state = interviewStateFromSession(session);
  assert.equal(state.status, 'content_blocked');
  assert.equal(state.progressionBlocked, true);
  assert.equal(state.progressionBlockedReason, 'No matching inventory.');
  assert.equal(state.currentScore, 70);
  assert.equal(state.currentFeedback, 'Review atomicity');
});
