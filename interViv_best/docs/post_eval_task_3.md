# Post-Eval Task 3 - Webcam Engagement Classification

Status: implemented and smoke-tested

## What changed

- Installed `face-api.js`.
- Added four face-api model files under `frontend/public/models/`.
- Added `frontend/src/lib/engagement.js`.
- Wired `Interview.jsx` to load models, sample camera frames while answering, show a live engagement indicator, and submit `engagement_label` plus `engagement_confidence`.
- `submitAnswer()` now normalizes missing engagement fields to `null`.

## Graceful Degradation

- Camera off or blocked: `engagement_label=null`, `engagement_confidence=null`.
- Model load failure: indicator shows unavailable, interview remains text/mic usable.
- No face or no valid samples: engagement payload stays null.

## Verified

- `npm run build` completed successfully.
- Model manifests were served by Vite with HTTP 200.
- `modeOfLabels()` returns `High` for high-expression samples and `null` for empty/NoFace samples.
- In-app browser smoke with camera blocked showed `Engagement Off` and no crash. Screenshot: `docs/task3_camera_blocked.png`.
- Browser console showed only React Router future-flag warnings, no engagement/model errors.

## Limitation

The in-app browser blocked camera permission in this environment, so I could not physically prove the "smiling face -> High within 4s" path with a real webcam. The mapping is implemented in `classifyFrame()` as `happy -> High`, and the aggregation path was verified with direct sample data.
