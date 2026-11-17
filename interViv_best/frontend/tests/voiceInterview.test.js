import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { createRecognitionController } from '../src/lib/speech/stt.js';
import { deliverySignals } from '../src/lib/speech/stt.js';
import { createSpeaker } from '../src/lib/speech/tts.js';
import { pickEnglishVoice, rankEnglishVoices, readStoredVoiceName, selectVoiceName, writeStoredVoiceName } from '../src/lib/speech/voiceChoice.js';
import { CLOSING_LINE, FOLLOW_UP_LINE, GREETING_LINE, attachInterviewSpeech, interviewerLines } from '../src/lib/speech/interviewerScript.js';
import { deliveryAnswerLabel, deliveryReport, fillerCount, paceCell, speakingCell } from '../src/lib/speech/deliveryReport.js';
import { createPresenceSampler } from '../src/lib/speech/presence.js';
import { isVoiceInterview, markVoiceInterview, speechInputMode } from '../src/lib/speech/voiceSession.js';
import { quickInterviewPayload } from '../src/lib/stagedSession.js';

const VOICES = [
  { name: 'Premium Samantha', lang: 'en-US', localService: false },
  { name: 'Enhanced Alex', lang: 'en-US', localService: true },
  { name: 'Google UK English Female', lang: 'en-GB', localService: false },
  { name: 'Google US English', lang: 'en-US', localService: false },
  { name: 'Local', lang: 'en-US', localService: true },
  { name: 'Remote', lang: 'en-GB', localService: false },
  { name: 'Premium Deutsch', lang: 'de-DE', localService: true },
];

function mockSpeech(voices) {
  const spoken = [];
  class Utterance { constructor(text) { this.text = text; } }
  const win = {
    SpeechSynthesisUtterance: Utterance,
    speechSynthesis: {
      speak: utterance => { spoken.push(utterance); utterance.onstart?.(); },
      cancel: () => {},
      getVoices: () => voices,
    },
  };
  return { win, spoken };
}

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

test('English voices prefer Premium, then Enhanced, then Google, then local, then any English', () => {
  assert.deepEqual(rankEnglishVoices(VOICES).map(voice => voice.name), [
    'Premium Samantha', 'Enhanced Alex', 'Google UK English Female', 'Google US English', 'Local', 'Remote',
  ]);
  assert.equal(pickEnglishVoice(VOICES, '').name, 'Premium Samantha');
  assert.equal(pickEnglishVoice(VOICES, 'Local').name, 'Local');
  assert.equal(selectVoiceName([], ''), '');
  assert.equal(selectVoiceName(VOICES, ''), 'Premium Samantha');
  assert.equal(selectVoiceName(VOICES, 'Google US English'), 'Google US English');
});

test('stored voice name survives a throwing storage API', () => {
  let saved = null;
  writeStoredVoiceName('Local', (_name, value) => { saved = value; });
  assert.equal(readStoredVoiceName(() => saved), 'Local');
  assert.equal(readStoredVoiceName(() => { throw new Error('blocked'); }), '');
  writeStoredVoiceName('Local', () => { throw new Error('blocked'); });
});

test('default read-aloud still uses the first local English voice and rate 1', () => {
  const { win, spoken } = mockSpeech(VOICES);
  const speaker = createSpeaker({ win });
  assert.equal(speaker.speak('Hello'), true);
  assert.equal(spoken[0].voice.name, 'Enhanced Alex');
  assert.equal(spoken[0].rate, 1);
});

test('scripted lines greet once, name the skill, and use the follow-up sentence', () => {
  assert.deepEqual(interviewerLines({ stage: 'warm_up', question: 'What is a list?', greeted: false }), [GREETING_LINE, 'What is a list?']);
  assert.deepEqual(interviewerLines({ stage: 'warm_up', question: 'What is a list?', greeted: true }), ['What is a list?']);
  assert.deepEqual(interviewerLines({ stage: 'core', skill: 'Python', question: 'Explain a lock.' }), ["Let's talk about Python.", 'Explain a lock.']);
  assert.deepEqual(interviewerLines({ stage: 'core', skill: 'Python', question: 'And the return value?', isFollowUp: true }), [FOLLOW_UP_LINE, 'And the return value?']);
  assert.equal(FOLLOW_UP_LINE, 'Let me follow up on that.');
  assert.match(CLOSING_LINE, /not part of your score/i);
});

test('interviewer speech pauses recognition until the last line ends', () => {
  const { win, spoken } = mockSpeech(VOICES);
  const { FakeRecognition, instances } = fakeRecognition();
  const recognition = createRecognitionController({
    Recognition: FakeRecognition, onResult() {}, onState() {}, schedule: fn => fn(),
  });
  let speech;
  const speaker = createSpeaker({
    win,
    chooseVoice: voices => pickEnglishVoice(voices, ''),
    onEnd: () => speech.ended(),
  });
  speech = attachInterviewSpeech({ speaker, recognition });
  recognition.start();
  const rec = instances[0];
  speech.play([GREETING_LINE, 'What is a list?']);
  assert.equal(rec.starts, 1);
  assert.equal(rec.stops, 1);
  assert.equal(spoken[0].text, GREETING_LINE);
  assert.equal(spoken[0].rate, 0.95);
  assert.equal(spoken[0].voice.name, 'Premium Samantha');
  spoken[0].onend();
  assert.equal(spoken[1].text, 'What is a list?');
  assert.equal(rec.starts, 1, 'still paused during the question');
  spoken[1].onend();
  assert.equal(rec.starts, 2, 'listening resumes after the question');

  speech.play(['Hello again.', 'Next question.']);
  const starts = rec.starts;
  speech.cancel();
  spoken.at(-1).onend();
  assert.equal(spoken.length, 3);
  assert.equal(rec.starts, starts);
  assert.equal(speech.queue.active, false);
});

test('delivery notes count fillers, pace and face presence without a score', () => {
  const text = 'Um I uh you know basically erm understand this topic well enough now';
  assert.equal(fillerCount(text), 5);
  assert.equal(fillerCount('A humble approach'), 0);
  const report = deliveryReport({ text, speakingMs: 15000, faceSamples: [1, 0, 2] });
  assert.equal(report.words, deliverySignals(text, 15000).words);
  assert.equal(report.wpm, deliverySignals(text, 15000).wpm);
  assert.equal(report.fillerWords, 5);
  assert.equal(report.faceVisiblePercent, 67);
  assert.equal(report.multipleFaceSamples, 1);
  const brief = deliveryReport({ text: 'humble', speakingMs: 2000, faceSamples: [] });
  assert.equal(brief.wpm, null);
  assert.equal(brief.fillerWords, 0);
  assert.equal(brief.faceVisiblePercent, null);
  assert.equal(deliveryAnswerLabel({ stage: 'warm_up', skill: 'Python' }), 'Warm-up');
  assert.equal(deliveryAnswerLabel({ stage: 'core', skill: 'Python' }), 'Python');
  assert.equal(deliveryAnswerLabel({ stage: 'follow_up', skill: 'Python' }), 'Python follow-up');
  assert.equal(deliveryAnswerLabel({ stage: 'core', skill: 'Agile', isFollowUp: true }), 'Agile follow-up');
  assert.equal(deliveryAnswerLabel({ stage: 'warm_up' }), 'Warm-up');
  assert.equal(speakingCell(0), 'Typed');
  assert.equal(speakingCell(12500), '12.5 s');
  assert.equal(paceCell({ speakingMs: 0, wpm: 120 }), '—');
  assert.equal(paceCell({ speakingMs: 15000, wpm: 52 }), '52');
});

test('presence sampling uses the mocked camera and ignores a frame that is not ready', async () => {
  let scheduled = null;
  const seen = [];
  const sampler = createPresenceSampler({
    detectFaces: video => { seen.push(video.id); return video.faces; },
    schedule: fn => { scheduled = fn; return 7; },
    clear: () => { scheduled = null; },
  });
  sampler.attach({ id: 'blank' });
  await sampler.start();
  assert.deepEqual(sampler.samples(), []);
  sampler.attach({ id: 'cam', videoWidth: 32, faces: 2 });
  await scheduled();
  assert.deepEqual(sampler.samples(), [2]);
  assert.deepEqual(seen, ['cam']);
  sampler.stop();
  assert.equal(scheduled, null);
});

test('presence loading never references the expression model', () => {
  const source = readFileSync(new URL('../src/lib/speech/presence.js', import.meta.url), 'utf8');
  assert.equal(source.includes('faceExpression'), false);
  assert.equal(source.includes('withFaceExpressions'), false);
  assert.equal(source.includes('tinyFaceDetector'), true);
});

test('speech input falls back from browser recognition to server transcription to typing', () => {
  assert.equal(speechInputMode({ recognitionAvailable: true, transcriptionAvailable: true }), 'browser');
  assert.equal(speechInputMode({ recognitionAvailable: false, transcriptionAvailable: true }), 'server');
  assert.equal(speechInputMode({ recognitionAvailable: false, transcriptionAvailable: false }), 'type');
});

test('voice interview is off unless that session was explicitly started with it', () => {
  let saved = null;
  const read = () => saved;
  const write = (_name, value) => { saved = value; };
  assert.equal(isVoiceInterview('session-a', read), false);
  markVoiceInterview('session-a', false, read, write);
  assert.equal(isVoiceInterview('session-a', read), false);
  markVoiceInterview('session-a', true, read, write);
  markVoiceInterview('session-b', true, read, write);
  assert.equal(isVoiceInterview('session-a', read), true);
  assert.equal(isVoiceInterview('session-b', read), true);
  markVoiceInterview('session-a', false, read, write);
  assert.equal(isVoiceInterview('session-a', read), false);
  assert.equal(isVoiceInterview('session-b', read), true);
  const payload = quickInterviewPayload({ skills: ['Python'] });
  assert.equal(Object.hasOwn(payload, 'voice'), false);
  assert.equal(Object.hasOwn(payload, 'voice_interview'), false);
});
