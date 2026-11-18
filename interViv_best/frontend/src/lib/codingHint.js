/**
 * Body for POST /problems/coach/hint.
 * last_error is the runner failure, or the first failed visible example only.
 * Hidden tests are never included.
 */

const RUNNER_ERRORS = new Set(['compile', 'timeout', 'runtime']);

export function codingHintLastError({ runnerError, visible, tests } = {}) {
  const runner = String(runnerError || '').trim();
  if (runner) return runner;
  const cases = Array.isArray(visible) ? visible : [];
  const index = cases.findIndex((item) => item && item.passed === false);
  if (index < 0) return null;
  const item = cases[index] || {};
  const kind = String(item.error || '');
  if (RUNNER_ERRORS.has(kind)) {
    const message = String(item.message || '').trim();
    return message ? `${kind}: ${message}` : kind;
  }
  const test = (Array.isArray(tests) ? tests : [])[index] || {};
  const input = test.input && Object.prototype.hasOwnProperty.call(test.input, 'args')
    ? test.input.args
    : (test.input === undefined ? null : test.input);
  return JSON.stringify({
    input,
    expected: Object.prototype.hasOwnProperty.call(test, 'expected') ? test.expected : null,
    actual: Object.prototype.hasOwnProperty.call(item, 'actual') ? item.actual : null,
  });
}

export function codingHintPayload({
  sessionId,
  round,
  level,
  source,
  language,
  runnerError,
  visible,
  tests,
}) {
  return {
    session_id: sessionId,
    round,
    level,
    source: source || '',
    language: language || '',
    last_error: codingHintLastError({ runnerError, visible, tests }),
  };
}
