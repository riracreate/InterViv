import { useCallback, useEffect, useRef, useState } from "react";

const MODEL_URL =
  "https://cdn.jsdelivr.net/npm/@vladmandic/face-api@1.7.15/model/";

const INTERVAL_MS = 2000;

// Low brightness threshold (0-255 luminance scale)
const LOW_BRIGHTNESS_THRESHOLD = 50;

/**
 * Compute average luminance of the current video frame.
 * Samples a small 32×24 thumbnail for performance.
 * Returns a value in [0, 255].
 */
function sampleBrightness(videoEl) {
  try {
    const canvas = document.createElement("canvas");
    canvas.width = 32;
    canvas.height = 24;
    const ctx = canvas.getContext("2d");
    if (!ctx) return 128;
    ctx.drawImage(videoEl, 0, 0, 32, 24);
    const { data } = ctx.getImageData(0, 0, 32, 24);
    let sum = 0;
    for (let i = 0; i < data.length; i += 4) {
      sum += 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
    }
    return sum / (32 * 24);
  } catch {
    return 128;
  }
}

/**
 * Map face-api expression probabilities to an engagement label.
 * Returns 'High Engagement', 'Low Engagement', or 'Neutral'.
 */
function expressionsToLabel(expressions) {
  const high =
    (expressions.happy ?? 0) + (expressions.surprised ?? 0);
  const low =
    (expressions.sad ?? 0) +
    (expressions.angry ?? 0) +
    (expressions.fearful ?? 0) +
    (expressions.disgusted ?? 0);
  if (high > 0.5) return "High Engagement";
  if (low > 0.5) return "Low Engagement";
  return "Neutral";
}

/**
 * useEngagementDetection
 *
 * Loads TinyFaceDetector + FaceExpressionNet via @vladmandic/face-api from CDN,
 * analyses webcam frames every INTERVAL_MS milliseconds, and keeps a running
 * tally so that getAggregatedLabel() returns the dominant label for the full
 * session.
 *
 * @param {{ videoRef: React.RefObject, enabled?: boolean }} opts
 * @returns {{
 *   engagementLabel: string,
 *   modelsLoaded: boolean,
 *   modelError: Error|null,
 *   lowLight: boolean,
 *   getAggregatedLabel: () => string,
 *   resetCounts: () => void,
 * }}
 */
export function useEngagementDetection({ videoRef, enabled = true }) {
  const [engagementLabel, setEngagementLabel] = useState("Neutral");
  const [modelsLoaded, setModelsLoaded] = useState(false);
  const [modelError, setModelError] = useState(null);
  const [lowLight, setLowLight] = useState(false);

  const faceapiRef = useRef(null);
  const countsRef = useRef({ total: 0, high: 0, low: 0 });
  const intervalRef = useRef(null);

  // ── Load models once ────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const faceapi = await import("@vladmandic/face-api");
        await Promise.all([
          faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL),
          faceapi.nets.faceExpressionNet.loadFromUri(MODEL_URL),
        ]);
        if (!cancelled) {
          faceapiRef.current = faceapi;
          setModelsLoaded(true);
        }
      } catch (err) {
        if (!cancelled) {
          setModelError(err instanceof Error ? err : new Error(String(err)));
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  // ── Per-frame analysis ──────────────────────────────────────
  const analyzeFrame = useCallback(async () => {
    const video = videoRef?.current;
    const faceapi = faceapiRef.current;
    if (!video || !faceapi || video.readyState < 2) return;

    const brightness = sampleBrightness(video);
    setLowLight(brightness < LOW_BRIGHTNESS_THRESHOLD);

    try {
      const detection = await faceapi
        .detectSingleFace(video, new faceapi.TinyFaceDetectorOptions())
        .withFaceExpressions();

      countsRef.current.total += 1;

      if (!detection) {
        countsRef.current.low += 1;
        setEngagementLabel("Low Engagement");
        return;
      }

      const label = expressionsToLabel(detection.expressions);
      if (label === "High Engagement") countsRef.current.high += 1;
      else if (label === "Low Engagement") countsRef.current.low += 1;
      setEngagementLabel(label);
    } catch {
      // Transient detection failure — keep previous label
    }
  }, [videoRef]);

  // ── Interval runner ─────────────────────────────────────────
  useEffect(() => {
    if (!enabled || !modelsLoaded) return;
    intervalRef.current = setInterval(analyzeFrame, INTERVAL_MS);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [enabled, modelsLoaded, analyzeFrame]);

  // ── Aggregate helper ────────────────────────────────────────
  const getAggregatedLabel = useCallback(() => {
    const { total, high, low } = countsRef.current;
    if (total === 0) return "Neutral";
    const highRatio = high / total;
    const lowRatio = low / total;
    if (highRatio > 0.5) return "High Engagement";
    if (lowRatio > 0.5) return "Low Engagement";
    if (highRatio + lowRatio < 0.3) return "Neutral";
    return "Uncertain";
  }, []);

  const resetCounts = useCallback(() => {
    countsRef.current = { total: 0, high: 0, low: 0 };
  }, []);

  return {
    engagementLabel,
    modelsLoaded,
    modelError,
    lowLight,
    getAggregatedLabel,
    resetCounts,
  };
}
