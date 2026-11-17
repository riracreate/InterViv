import { deliverySignals } from './stt.js';

const FILLERS = [/\bum\b/gi, /\buh\b/gi, /\berm\b/gi, /\byou know\b/gi, /\bbasically\b/gi];

/** Count filler words. Whole words only, so "humble" is not "um". */
export function fillerCount(text) {
  const source = String(text || '');
  return FILLERS.reduce((total, pattern) => total + (source.match(pattern) || []).length, 0);
}

export function deliveryReport({ text = '', speakingMs = 0, faceSamples = [] } = {}) {
  const signals = deliverySignals(text, Number(speakingMs) || 0);
  const samples = Array.isArray(faceSamples) ? faceSamples : [];
  const visible = samples.filter(count => Number(count) >= 1).length;
  return {
    speakingMs: Number(speakingMs) || 0,
    words: signals.words,
    wpm: signals.wpm,
    fillerWords: fillerCount(text),
    faceVisiblePercent: samples.length ? Math.round((visible / samples.length) * 100) : null,
    multipleFaceSamples: samples.filter(count => Number(count) > 1).length,
  };
}
