export const GREETING_LINE = "Hello. I'll ask a short warm-up, then a few questions on the skills you chose. Take your time.";
export const FOLLOW_UP_LINE = 'Let me follow up on that.';
export const CLOSING_LINE = "That's the end of this interview. Your delivery notes are on this screen and are not part of your score.";

/** Scripted interviewer lines only. No model text. */
export function interviewerLines({ stage, skill, question, isFollowUp = false, greeted = false } = {}) {
  const lines = [];
  if (isFollowUp || stage === 'follow_up') lines.push(FOLLOW_UP_LINE);
  else if (stage === 'core') lines.push(`Let's talk about ${skill || 'this skill'}.`);
  else if (stage === 'warm_up' && !greeted) lines.push(GREETING_LINE);
  const prompt = String(question || '').trim();
  if (prompt) lines.push(prompt);
  return lines;
}

/**
 * Speak scripted lines one after another.
 * completeCurrent() is called from the speaker's end callback.
 */
export function createSpeakQueue(speaker, { rate = 0.95, onLine } = {}) {
  let lines = [];
  let index = 0;
  let running = false;
  let generation = 0;
  let suppress = false;

  function pump(gen) {
    if (!running || gen !== generation) return;
    if (index >= lines.length) {
      running = false;
      return;
    }
    const text = lines[index];
    onLine?.(text);
    if (!speaker.speak(text, { rate })) {
      index += 1;
      pump(gen);
    }
  }

  return {
    start(next) {
      generation += 1;
      running = false;
      suppress = true;
      try { speaker.cancel?.(); } finally { suppress = false; }
      lines = (Array.isArray(next) ? next : []).map(line => String(line || '').trim()).filter(Boolean);
      index = 0;
      running = lines.length > 0;
      pump(generation);
    },
    completeCurrent() {
      if (!running) return 'idle';
      index += 1;
      if (index >= lines.length) {
        running = false;
        return 'done';
      }
      pump(generation);
      return running ? 'speaking' : 'done';
    },
    cancel() {
      generation += 1;
      running = false;
      speaker.cancel?.();
    },
    get active() { return running; },
    get suppress() { return suppress; },
  };
}

/** Wire scripted speech to recognition: paused while the interviewer speaks. */
export function attachInterviewSpeech({ speaker, recognition, onSpeaking, onCaption, rate = 0.95 }) {
  const queue = createSpeakQueue(speaker, { rate, onLine: onCaption });
  return {
    queue,
    play(lines) {
      recognition?.pause?.();
      onSpeaking?.(true);
      queue.start(lines);
      if (!queue.active) {
        onSpeaking?.(false);
        if (recognition?.wantsRecording) recognition.resume?.();
      }
    },
    ended() {
      if (queue.suppress) return 'idle';
      const status = queue.completeCurrent();
      if (status === 'speaking') return status;
      onSpeaking?.(false);
      if (status === 'done' && recognition?.wantsRecording) recognition.resume?.();
      return status;
    },
    cancel() {
      queue.cancel();
      onSpeaking?.(false);
    },
  };
}
