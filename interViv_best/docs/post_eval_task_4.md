# Post-Eval Task 4 - Baseline Calibration

Status: implemented and smoke-tested

## What changed

- Added a first-round calibration screen before the first question when the camera is available.
- Calibration samples one frame per second for 10 seconds and stores the baseline with `modeOfLabels()`.
- Added a `Skip` path that uses Neutral as the baseline and forces `engagement_delta=0`.
- Added `computeEngagementDelta()` with order `Low=0`, `Uncertain=0`, `Neutral=1`, `High=2`.
- Frontend now sends `engagement_label`, `engagement_confidence`, and `engagement_delta`.
- Backend accepts and persists `engagement_confidence` and `engagement_delta` with the round document.

## Verified

- `npm run build` completed successfully.
- Backend request model accepts `engagement_delta`.
- Memory-DB smoke persisted a calibrated round with `engagement_label=High` and `engagement_delta=1`.
- Memory-DB smoke persisted a skipped-calibration round with `engagement_label=High` and `engagement_delta=0`.
- In-app browser camera-blocked smoke showed `Baseline Skipped`, `Engagement Off`, and no crash. Screenshot: `docs/task4_camera_blocked_skip.png`.

## Limitation

The in-app browser blocks camera permission in this environment, so the real 10-second webcam calibration path could not be physically completed here. The implemented timer/sampling path is present in `Interview.jsx`; backend persistence was verified with the memory DB.
