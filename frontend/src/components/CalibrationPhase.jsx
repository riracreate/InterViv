import { useEffect, useRef, useState } from "react";

const CALIBRATION_SECONDS = 10;
const LOW_BRIGHTNESS_THRESHOLD = 50;

/**
 * Sample average luminance (0-255) from the current video frame.
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
 * CalibrationPhase
 *
 * A 10-second countdown screen shown before the first interview question.
 * - Requests webcam access and shows a live preview.
 * - Samples brightness each second and warns the user if lighting is too low.
 * - After the countdown, calls `onComplete({ brightnessBaseline })` so the
 *   parent can store the calibration data.
 * - If camera permission is denied the user can still skip calibration.
 *
 * Props:
 *   onComplete(data)  – called when the countdown finishes or the user skips.
 *                       data = { brightnessBaseline: number | null }
 */
function CalibrationPhase({ onComplete }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const timerRef = useRef(null);

  const [secondsLeft, setSecondsLeft] = useState(CALIBRATION_SECONDS);
  const [cameraError, setCameraError] = useState(null);
  const [lowLight, setLowLight] = useState(false);
  const brightnessReadings = useRef([]);

  // ── Start webcam ────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;

    async function startCamera() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "user", width: { ideal: 320 }, height: { ideal: 240 } },
          audio: false,
        });
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
      } catch (err) {
        if (!cancelled) {
          setCameraError(
            err.name === "NotAllowedError"
              ? "Camera permission denied."
              : "Could not access the camera."
          );
        }
      }
    }

    startCamera();

    return () => {
      cancelled = true;
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
      }
    };
  }, []);

  // ── Countdown + brightness sampling ─────────────────────────
  useEffect(() => {
    timerRef.current = setInterval(() => {
      const video = videoRef.current;
      if (video && video.readyState >= 2) {
        const brightness = sampleBrightness(video);
        brightnessReadings.current.push(brightness);
        setLowLight(brightness < LOW_BRIGHTNESS_THRESHOLD);
      }

      setSecondsLeft((prev) => {
        if (prev <= 1) {
          clearInterval(timerRef.current);
          const readings = brightnessReadings.current;
          const baseline =
            readings.length > 0
              ? readings.reduce((a, b) => a + b, 0) / readings.length
              : null;
          // Stop the camera stream before calling onComplete
          if (streamRef.current) {
            streamRef.current.getTracks().forEach((t) => t.stop());
          }
          onComplete({ brightnessBaseline: baseline });
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timerRef.current);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleSkip() {
    clearInterval(timerRef.current);
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
    }
    onComplete({ brightnessBaseline: null });
  }

  const progress = ((CALIBRATION_SECONDS - secondsLeft) / CALIBRATION_SECONDS) * 100;

  return (
    <div className="app-shell flex items-center justify-center">
      <div className="glass-panel w-full max-w-xl overflow-hidden">
        <div className="bg-halo p-8">
          <p className="section-title">Calibration Phase</p>
          <h1 className="mt-3 text-3xl font-bold">
            Establishing your baseline
          </h1>
          <p className="mt-2 text-sm text-ink/70">
            Sit naturally and look at the camera for {CALIBRATION_SECONDS} seconds.
            This captures your resting face to personalise your engagement score.
          </p>
        </div>

        <div className="p-8 space-y-6">
          {/* Camera preview */}
          <div className="relative overflow-hidden rounded-[20px] bg-ink aspect-video flex items-center justify-center">
            {cameraError ? (
              <p className="text-sm text-white/70 px-6 text-center">{cameraError}</p>
            ) : (
              <video
                ref={videoRef}
                autoPlay
                muted
                playsInline
                className="w-full h-full object-cover scale-x-[-1]"
              />
            )}

            {/* Countdown overlay */}
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <div className="rounded-full bg-black/50 w-20 h-20 flex items-center justify-center backdrop-blur-sm">
                <span className="text-4xl font-bold text-white">{secondsLeft}</span>
              </div>
            </div>
          </div>

          {/* Progress bar */}
          <div className="h-2 rounded-full bg-ink/10 overflow-hidden">
            <div
              className="h-full rounded-full bg-ocean transition-all duration-1000"
              style={{ width: `${progress}%` }}
            />
          </div>

          {/* Lighting warning */}
          {lowLight && (
            <div className="rounded-2xl border border-ember/30 bg-ember/10 px-4 py-3 text-sm text-ember">
              ⚠️ Lighting is too low. Move closer to a light source for more
              accurate engagement detection.
            </div>
          )}

          {/* Status */}
          <div className="flex items-center justify-between">
            <p className="text-sm text-ink/60">
              {cameraError
                ? "Camera unavailable — engagement detection will use default scores."
                : secondsLeft > 0
                ? "Capturing resting face baseline…"
                : "Calibration complete!"}
            </p>
            <button
              className="secondary-button text-sm"
              onClick={handleSkip}
              type="button"
            >
              Skip
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default CalibrationPhase;
