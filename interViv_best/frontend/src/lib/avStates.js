/**
 * Distinct AV unavailable / capture states for Interview UI.
 * Pure helpers — no scores, no fabricated transcripts.
 */

export const AV_STATES = Object.freeze({
  PERMISSION_NOT_REQUESTED: 'permission_not_requested',
  PERMISSION_DENIED: 'permission_denied',
  NO_DEVICE: 'no_device',
  UNSUPPORTED_BROWSER: 'unsupported_browser',
  SERVICE_UNAVAILABLE: 'service_unavailable',
  CAPTURE_FAILED: 'capture_failed',
  INTERRUPTED_RECOVERABLE: 'interrupted_recoverable',
  READY: 'ready',
});

export function classifyMediaError(error, {
  secureContext = true,
  hasMediaDevices = typeof navigator !== 'undefined'
    && Boolean(navigator.mediaDevices?.getUserMedia),
} = {}) {
  if (!hasMediaDevices) {
    return AV_STATES.UNSUPPORTED_BROWSER;
  }
  if (!secureContext) {
    return AV_STATES.UNSUPPORTED_BROWSER;
  }
  const name = error?.name || '';
  if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
    return AV_STATES.PERMISSION_DENIED;
  }
  if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
    return AV_STATES.NO_DEVICE;
  }
  if (name === 'NotReadableError' || name === 'TrackStartError' || name === 'AbortError') {
    return AV_STATES.CAPTURE_FAILED;
  }
  return AV_STATES.CAPTURE_FAILED;
}

export function avStateLabel(state) {
  switch (state) {
    case AV_STATES.PERMISSION_NOT_REQUESTED:
      return 'Microphone permission not yet requested';
    case AV_STATES.PERMISSION_DENIED:
      return 'Microphone permission denied';
    case AV_STATES.NO_DEVICE:
      return 'No microphone device present';
    case AV_STATES.UNSUPPORTED_BROWSER:
      return 'Browser does not support media capture';
    case AV_STATES.SERVICE_UNAVAILABLE:
      return 'Transcription service unavailable';
    case AV_STATES.CAPTURE_FAILED:
      return 'Capture failed mid-session';
    case AV_STATES.INTERRUPTED_RECOVERABLE:
      return 'Capture interrupted — you can retry';
    case AV_STATES.READY:
      return 'Capture ready';
    default:
      return 'Unknown media state';
  }
}

/** Transcription failure must never invent text or a speech score. */
export function transcriptionFailureResult(statusCode) {
  return {
    ok: false,
    state: AV_STATES.SERVICE_UNAVAILABLE,
    transcript: null,
    speech_score: null,
    retryable: true,
    statusCode: statusCode || 503,
  };
}
