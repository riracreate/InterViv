// face-api.js is ~600KB minified; import it lazily so it only downloads
// when engagement detection actually starts (Interview route), not on
// first page load or dashboard chunks.
let faceapi = null;
let modelsLoaded = false;
let modelLoadFailed = false;
let modelLoadPromise = null;

const ENGAGEMENT_ORDER = {
  Low: 0,
  Uncertain: 0,
  Neutral: 1,
  High: 2,
};

export async function loadModels() {
  if (modelsLoaded || modelLoadFailed) return modelsLoaded;
  if (modelLoadPromise) return modelLoadPromise;

  modelLoadPromise = (async () => {
    try {
      faceapi = await import('face-api.js');
      await faceapi.nets.tinyFaceDetector.loadFromUri('/models');
      await faceapi.nets.faceExpressionNet.loadFromUri('/models');
      modelsLoaded = true;
    } catch (e) {
      console.warn('engagement load failed', e);
      modelLoadFailed = true;
    }
    return modelsLoaded;
  })();

  return modelLoadPromise;
}

export async function classifyFrame(video) {
  if (!modelsLoaded || !video) return null;
  if (!video.videoWidth || !video.videoHeight) return null;

  try {
    const det = await faceapi
      .detectSingleFace(video, new faceapi.TinyFaceDetectorOptions())
      .withFaceExpressions();

    if (!det) return { label: 'NoFace', confidence: 0 };

    const exp = det.expressions;
    const top = Object.entries(exp).sort((a, b) => b[1] - a[1])[0];
    const map = {
      happy: 'High',
      neutral: 'Neutral',
      surprised: 'High',
      sad: 'Low',
      angry: 'Low',
      fearful: 'Low',
      disgusted: 'Low',
    };
    const label = map[top[0]] || 'Neutral';
    return { label: top[1] < 0.4 ? 'Uncertain' : label, confidence: top[1] };
  } catch (e) {
    return null;
  }
}

export function modeOfLabels(samples) {
  const valid = samples.filter(s => s && s.label !== 'NoFace');
  if (!valid.length) return null;

  const counts = {};
  valid.forEach(s => {
    counts[s.label] = (counts[s.label] || 0) + 1;
  });
  const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  return {
    label: sorted[0][0],
    confidence: valid.reduce((a, s) => a + s.confidence, 0) / valid.length,
    sample_count: valid.length,
  };
}

export function computeEngagementDelta(currentLabel, baselineLabel) {
  if (!(currentLabel in ENGAGEMENT_ORDER) || !(baselineLabel in ENGAGEMENT_ORDER)) {
    return null;
  }

  const current = ENGAGEMENT_ORDER[currentLabel];
  const baseline = ENGAGEMENT_ORDER[baselineLabel];
  if (current > baseline) return 1;
  if (current < baseline) return -1;
  return 0;
}
