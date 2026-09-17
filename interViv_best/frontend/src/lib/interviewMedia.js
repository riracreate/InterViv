/**
 * Interview media gate — camera/mic/calibration only for interview-style
 * technical rounds. MCQ and SQL never open the camera.
 */

export function blockUsesInterviewMedia(category, roundType) {
  const c = String(category || '').toLowerCase();
  const t = String(roundType || '').toLowerCase();
  if (t === 'mcq' || t === 'coding' || t === 'ml_primitives' || t === 'sql') return false;
  if (c === 'verbal' || c === 'oa' || c === 'coding' || c === 'ml_primitives' || c === 'sql') {
    return false;
  }
  if (c) return true;
  return t === 'technical_short_answer' || t === 'system_design';
}

export function stopMediaStream(stream) {
  stream?.getTracks?.().forEach((track) => track.stop());
}

export function mediaErrorMessage(error, device) {
  if (typeof navigator !== 'undefined' && !navigator.mediaDevices?.getUserMedia) {
    return `${device} access is not supported in this browser.`;
  }
  if (
    typeof window !== 'undefined'
    && !window.isSecureContext
    && !['localhost', '127.0.0.1'].includes(window.location.hostname)
  ) {
    return `${device} access requires HTTPS or localhost.`;
  }
  if (error?.name === 'NotAllowedError' || error?.name === 'PermissionDeniedError') {
    return `${device} permission was blocked. Allow access in the browser and try again.`;
  }
  if (error?.name === 'NotFoundError' || error?.name === 'DevicesNotFoundError') {
    return `No ${device.toLowerCase()} device was found.`;
  }
  if (error?.name === 'NotReadableError' || error?.name === 'TrackStartError') {
    return `${device} is already in use by another app.`;
  }
  return `${device} could not be started.`;
}
