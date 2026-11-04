// Phase 6: voice is optional and well-behaved. Fake browser APIs only.
import assert from 'node:assert/strict';
import test from 'node:test';

import { createRecognitionController, deliverySignals, MAX_CONSECUTIVE_ERRORS } from '../src/lib/speech/stt.js';
import { createSpeaker, speechSynthesisSupported } from '../src/lib/speech/tts.js';

function fakeRecognition() {
  const instances = [];
  class FakeRecognition {
    constructor() { this.starts = 0; this.stops = 0; instances.push(this); }
    start() { this.starts += 1; }
    stop() { this.stops += 1; }
    abort() { this.aborted = true; }
  }
  return { FakeRecognition, instances };
}

function controllerWith() {
  const { FakeRecognition, instances } = fakeRecognition();
  const states = [];
  const results = [];
  const controller = createRecognitionController({
    Recognition: FakeRecognition,
    onResult: (finalText, interim) => results.push([finalText, interim]),
    onState: (state, detail) => states.push(detail ? `${state}:${detail}` : state),
    schedule: (fn) => fn(), // restart immediately in tests
  });
  return { controller, instances, states, results };
}

test('recognition restarts after a normal pause while recording is wanted', () => {
  const { controller, instances } = controllerWith();
  controller.start();
  const rec = instances[0];
  rec.onerror({ error: 'no-speech' });
  rec.onend();
  rec.onend();
  assert.equal(rec.starts, 3);
  assert.equal(controller.restartCount, 2);
  controller.stop();
  rec.onend();
  assert.equal(rec.starts, 3, 'no restart after an explicit stop');
});

test('permission errors and repeated failures stop retrying', () => {
  const denied = controllerWith();
  denied.controller.start();
  denied.instances[0].onerror({ error: 'not-allowed' });
  denied.instances[0].onend();
  assert.equal(denied.instances[0].starts, 1);
  assert.ok(denied.states.includes('error:not-allowed'));

  const flaky = controllerWith();
  flaky.controller.start();
  const rec = flaky.instances[0];
  for (let i = 0; i < MAX_CONSECUTIVE_ERRORS; i += 1) {
    rec.onerror({ error: 'network' });
    rec.onend();
  }
  assert.ok(flaky.states.includes('error:repeated'));
  assert.equal(flaky.controller.wantsRecording, false);
});

test('results reset the error count and stream final and interim text', () => {
  const { controller, instances, results } = controllerWith();
  controller.start();
  const rec = instances[0];
  rec.onerror({ error: 'network' });
  rec.onresult({ resultIndex: 0, results: [Object.assign([{ transcript: 'hello' }], { isFinal: true }), Object.assign([{ transcript: 'wor' }], { isFinal: false })] });
  rec.onerror({ error: 'network' });
  rec.onerror({ error: 'network' });
  assert.equal(controller.wantsRecording, true, 'only consecutive errors count');
  assert.deepEqual(results[0], ['hello ', 'wor']);
});

test('recognition holds while read-aloud speaks and resumes afterwards', () => {
  const { controller, instances, states } = controllerWith();
  controller.start();
  const rec = instances[0];
  controller.pause();
  rec.onend();
  assert.equal(rec.starts, 1, 'no restart while paused');
  assert.ok(states.includes('paused'));
  controller.resume();
  assert.equal(rec.starts, 2);
});

test('read-aloud speaks once, reports start/end, and cancel ends playback', () => {
  const spoken = [];
  let cancels = 0;
  class Utterance { constructor(text) { this.text = text; } }
  const win = {
    SpeechSynthesisUtterance: Utterance,
    speechSynthesis: {
      speak: (u) => { spoken.push(u); u.onstart?.(); },
      cancel: () => { cancels += 1; },
      getVoices: () => [{ lang: 'en-US', localService: true, name: 'Local' }],
    },
  };
  const events = [];
  const speaker = createSpeaker({ win, onStart: () => events.push('start'), onEnd: () => events.push('end') });
  assert.equal(speaker.supported, true);
  assert.equal(speaker.speak('  Explain indexing.  '), true);
  assert.equal(spoken[0].text, 'Explain indexing.');
  assert.equal(spoken[0].voice.name, 'Local');
  assert.equal(speaker.isSpeaking(), true);
  speaker.cancel();
  assert.deepEqual(events, ['start', 'end']);
  assert.equal(speaker.isSpeaking(), false);
  assert.ok(cancels >= 2);
  assert.equal(speaker.speak(''), false);
  assert.equal(speechSynthesisSupported({}), false);
  assert.equal(createSpeaker({ win: {} }).speak('hi'), false);
});

test('delivery signals: words, WPM from recorded time, advisory structure', () => {
  const text = 'An index is a sorted structure. However it costs writes, for example on bulk inserts into the orders table every night.';
  const signals = deliverySignals(text, 15000);
  assert.equal(signals.words, 21);
  assert.equal(signals.wpm, 84);
  assert.deepEqual(signals.checklist, { concept: true, tradeoff: true, example: true });
  assert.equal(deliverySignals('short answer', 2000).wpm, null); // under 10 s recorded
});
