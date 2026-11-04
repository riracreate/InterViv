import assert from 'node:assert/strict';
import test from 'node:test';
import { apiErrorMessage } from '../src/lib/api.js';

test('string detail is shown as-is', () => {
  assert.equal(apiErrorMessage({ detail: 'Unknown role' }), 'Unknown role');
});

test('validation error lists become field and message lines', () => {
  const message = apiErrorMessage({
    detail: [
      { loc: ['body', 'role_id'], msg: 'Input should be a valid string', type: 'string_type' },
      { loc: ['body', 'goal_text'], msg: 'Field required' },
    ],
  });
  assert.equal(message, 'role_id: Input should be a valid string\ngoal_text: Field required');
});

test('anything else is a generic message', () => {
  assert.equal(apiErrorMessage({ detail: { code: 1 } }), 'Something went wrong');
  assert.equal(apiErrorMessage({}), 'Something went wrong');
  assert.equal(apiErrorMessage(null), 'Something went wrong');
});
