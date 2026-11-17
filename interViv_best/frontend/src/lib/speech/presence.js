/**
 * Browser-only face presence. Loads tinyFaceDetector and nothing else.
 * No expression model, no emotion labels, no frames leave the browser.
 */

let faceapi = null;
let loaded = false;
let loading = null;
let failed = false;

export async function detectFaceCount(video) {
  if (failed || !video?.videoWidth || !video?.videoHeight) return null;
  if (!loaded) {
    if (!loading) {
      loading = (async () => {
        faceapi = await import('face-api.js');
        await faceapi.nets.tinyFaceDetector.loadFromUri('/models');
        loaded = true;
      })();
    }
    try {
      await loading;
    } catch {
      loading = null;
      failed = true;
      return null;
    }
  }
  const faces = await faceapi.detectAllFaces(video, new faceapi.TinyFaceDetectorOptions());
  return Array.isArray(faces) ? faces.length : 0;
}

export function createPresenceSampler({ detectFaces, schedule = setInterval, clear = clearInterval, intervalMs = 1000 }) {
  let timer = null;
  let video = null;
  const samples = [];
  let closed = false;

  async function tick() {
    if (closed || !video?.videoWidth) return;
    try {
      const count = await detectFaces(video);
      if (!closed && count != null) samples.push(Number(count) || 0);
    } catch {
      if (!closed) samples.push(0);
    }
  }

  return {
    attach(next) { video = next; },
    start() {
      this.stop();
      closed = false;
      samples.length = 0;
      const pending = tick();
      timer = schedule(() => tick(), intervalMs);
      return pending;
    },
    stop() {
      closed = true;
      if (timer != null) clear(timer);
      timer = null;
    },
    samples() { return samples.slice(); },
  };
}
