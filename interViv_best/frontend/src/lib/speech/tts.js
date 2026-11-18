/**
 * Opt-in read-aloud (overhaul Phase 6) over the browser speechSynthesis API.
 * Callers cancel on submit, navigation and unmount; recognition is paused
 * while speaking (see stt.js) so the interviewer's voice is not transcribed.
 */

export function speechSynthesisSupported(win = globalThis.window) {
  return Boolean(win?.speechSynthesis && win?.SpeechSynthesisUtterance);
}

function englishVoice(win) {
  const voices = win.speechSynthesis.getVoices?.() || [];
  return voices.find((v) => /^en(-|_)/i.test(v.lang) && v.localService) || voices.find((v) => /^en/i.test(v.lang)) || null;
}

export function createSpeaker({ win = globalThis.window, onStart, onEnd, chooseVoice } = {}) {
  const supported = speechSynthesisSupported(win);
  let active = null;
  return {
    supported,
    speak(text, { rate = 1 } = {}) {
      const clean = String(text || '').trim();
      if (!supported || !clean) return false;
      win.speechSynthesis.cancel();
      const utterance = new win.SpeechSynthesisUtterance(clean.slice(0, 1200));
      utterance.lang = 'en-US';
      utterance.rate = rate;
      const voices = win.speechSynthesis.getVoices?.() || [];
      const voice = chooseVoice ? chooseVoice(voices) : englishVoice(win);
      if (voice) utterance.voice = voice;
      const finish = () => {
        if (active !== utterance) return;
        active = null;
        onEnd?.();
      };
      utterance.onstart = () => onStart?.();
      utterance.onend = finish;
      utterance.onerror = finish; // "canceled"/"interrupted" also end playback
      active = utterance;
      win.speechSynthesis.speak(utterance);
      return true;
    },
    cancel() {
      if (!supported) return;
      const wasActive = Boolean(active);
      active = null;
      win.speechSynthesis.cancel();
      if (wasActive) onEnd?.();
    },
    isSpeaking() {
      return Boolean(active);
    },
  };
}
