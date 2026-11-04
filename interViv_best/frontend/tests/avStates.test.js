import assert from 'node:assert/strict';
import test from 'node:test';

import {
  AV_STATES,
  classifyMediaError,
  transcriptionFailureResult,
  avStateLabel,
} from '../src/lib/avStates.js';

test('AV states are distinct and labeled', () => {
  const needed = [
    AV_STATES.PERMISSION_NOT_REQUESTED,
    AV_STATES.PERMISSION_DENIED,
    AV_STATES.NO_DEVICE,
    AV_STATES.UNSUPPORTED_BROWSER,
    AV_STATES.SERVICE_UNAVAILABLE,
    AV_STATES.CAPTURE_FAILED,
    AV_STATES.INTERRUPTED_RECOVERABLE,
  ];
  const labels = new Set(needed.map((s) => avStateLabel(s)));
  assert.equal(labels.size, needed.length);
});

test('media errors map to distinct states', () => {
  assert.equal(
    classifyMediaError({ name: 'NotAllowedError' }, { hasMediaDevices: true }),
    AV_STATES.PERMISSION_DENIED,
  );
  assert.equal(
    classifyMediaError({ name: 'NotFoundError' }, { hasMediaDevices: true }),
    AV_STATES.NO_DEVICE,
  );
  assert.equal(
    classifyMediaError({ name: 'NotReadableError' }, { hasMediaDevices: true }),
    AV_STATES.CAPTURE_FAILED,
  );
  assert.equal(
    classifyMediaError({ name: 'NotAllowedError' }, { hasMediaDevices: false }),
    AV_STATES.UNSUPPORTED_BROWSER,
  );
});

test('transcription failure never invents transcript or speech score', () => {
  const failure = transcriptionFailureResult(503);
  assert.equal(failure.transcript, null);
  assert.equal(failure.speech_score, null);
  assert.equal(failure.retryable, true);
  assert.equal(failure.state, AV_STATES.SERVICE_UNAVAILABLE);
});
