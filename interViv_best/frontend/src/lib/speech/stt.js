/**
 * Browser speech recognition controller (overhaul Phase 6).
 *
 * Continuous recognition ends on its own after silence; while the candidate
 * still wants to record, the controller restarts it. It stops for good on
 * permission/capture errors, on an explicit stop (submit, exit), or after
 * MAX_CONSECUTIVE_ERRORS errors in a row. It never opens a separate
 * getUserMedia stream (the recognizer owns the microphone).
 */

export const TERMINAL_ERRORS = new Set([
  'not-allowed', 'service-not-allowed', 'audio-capture', 'language-not-supported',
]);
export const MAX_CONSECUTIVE_ERRORS = 3;
export const RESTART_DELAY_MS = 250;

export function recognitionClass(win = globalThis.window) {
  return win?.SpeechRecognition || win?.webkitSpeechRecognition || null;
}

/**
 * @param {{
 *   Recognition: any, lang?: string,
 *   onResult: (finalText: string, interimText: string) => void,
 *   onState: (state: 'listening'|'paused'|'idle'|'error', detail?: string) => void,
 *   schedule?: (fn: () => void, ms: number) => any,
 * }} options
 */
export function createRecognitionController({ Recognition, lang = 'en-US', onResult, onState, schedule = setTimeout }) {
  let rec = null;
  let wants = false;
  let paused = false;
  let errors = 0;
  let restarts = 0;

  function ensure() {
    if (rec || !Recognition) return rec;
    rec = new Recognition();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = lang;
    rec.onresult = (event) => {
      errors = 0;
      let finalText = '';
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const text = event.results[i][0].transcript;
        if (event.results[i].isFinal) finalText += `${text} `;
        else interim += text;
      }
      onResult?.(finalText, interim);
    };
    rec.onerror = (event) => {
      const code = event?.error || 'unknown';
      if (code === 'aborted' && (!wants || paused)) return; // our own stop
      if (TERMINAL_ERRORS.has(code)) {
        wants = false;
        onState?.('error', code);
        return;
      }
      if (code === 'no-speech') return; // silence: onend restarts
      errors += 1;
      if (errors >= MAX_CONSECUTIVE_ERRORS) {
        wants = false;
        onState?.('error', 'repeated');
      }
    };
    rec.onend = () => {
      if (wants && !paused) {
        restarts += 1;
        schedule(() => { if (wants && !paused) safeStart(); }, RESTART_DELAY_MS);
        return;
      }
      if (!paused) onState?.('idle');
    };
    return rec;
  }

  function safeStart() {
    try {
      ensure()?.start();
      onState?.('listening');
    } catch (err) {
      if (err?.name !== 'InvalidStateError') {
        wants = false;
        onState?.('error', err?.name || 'start-failed');
      }
    }
  }

  return {
    supported: Boolean(Recognition),
    start() {
      if (!Recognition) return false;
      wants = true;
      paused = false;
      errors = 0;
      safeStart();
      return true;
    },
    stop() {
      wants = false;
      paused = false;
      try { rec?.stop(); } catch { /* already stopped */ }
      onState?.('idle');
    },
    /** Hold recognition while read-aloud plays; keeps the wish to record. */
    pause() {
      if (!wants || paused) return;
      paused = true;
      try { rec?.stop(); } catch { /* already stopped */ }
      onState?.('paused');
    },
    resume() {
      if (!wants || !paused) return;
      paused = false;
      safeStart();
    },
    abort() {
      wants = false;
      paused = false;
      try { rec?.abort(); } catch { /* never started */ }
    },
    get wantsRecording() { return wants; },
    /** Automatic restarts after silence (a rough pause count). */
    get restartCount() { return restarts; },
  };
}

/** Advisory delivery signals; never part of the score. */
export function deliverySignals(text, recordedMs) {
  const words = String(text || '').trim().split(/\s+/).filter(Boolean).length;
  const minutes = recordedMs / 60000;
  const wpm = minutes >= 10 / 60 && words > 0 ? Math.round(words / minutes) : null;
  const lower = String(text || '').toLowerCase();
  return {
    words,
    wpm,
    checklist: {
      concept: words >= 15,
      tradeoff: /\b(trade-?off|however|but|instead|cost|downside|versus|vs\.?)\b/.test(lower),
      example: /\b(for example|for instance|e\.g\.|such as|in my project|when i)\b/.test(lower),
    },
  };
}
