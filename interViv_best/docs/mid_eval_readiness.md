# Mid-Eval Readiness Smoke Test

Date: 2026-04-25
Mode: local FastAPI + Vite, `INTERVIV_USE_MEMORY_DB=true`
Session tested: `5af73bb5-2c9f-46ab-a652-3a4cc8bb48e5`
Candidate tested: `b777356e-0ad1-4c41-a195-9c4a1b18cf9c`

## Summary

Overall status: mostly pass, with environment limitations documented.

The core backend flow completed: PDF resume parse, 3-skill session start, 9 submitted rounds, scoring breakdowns, skill rotation, dashboard payload, engagement fields, and server STT. The dashboard renders in the browser after the Vite proxy fix.

## Smoke Results

| # | Test | Status | Evidence / Notes |
|---|------|--------|------------------|
| 1 | Upload PDF resume -> skills extracted | PASS | `/api/resume` returned 9 skills: Docker, JavaScript, Machine Learning, MongoDB, Python, REST, React, SQL, System Design. |
| 2 | Multi-skill chips, edit one, Start with 3 skills | PASS API / PARTIAL UI | Started 3-skill session with Python, React, SQL and `total_rounds=9`. Browser OS file picker could not be automated by the in-app browser, so chip editing after upload was not driven visually. |
| 3 | Camera permission prompt | PASS graceful | In-app browser blocked camera permission. Interview did not crash; UI showed camera blocked, `Engagement Off`, `Baseline Skipped`. |
| 4 | Calibration phase | PASS graceful / PARTIAL physical | With camera blocked, app auto-skipped calibration using Neutral baseline. Real 10-second webcam path is implemented but could not be physically completed in this browser. |
| 5 | First question loads | PASS | CSV-backed question loaded: "When would you use a generator instead of a list in Python?..." OpenRouter was not used for scoring. |
| 6 | Type and speak | PARTIAL | Typed answers submitted through `/session/answer`. Server STT passed through `/api/transcribe`. Browser STT could not be physically tested because mic permission is blocked in the in-app browser. |
| 7 | Engagement indicator updates live | PASS graceful / PARTIAL physical | Camera-blocked path shows `Engagement Off`; submitted rounds store engagement fields. Live face classification requires a browser with camera permission. |
| 8 | Submit -> feedback -> scoring breakdown panel | PASS | All 9 rounds submitted. Breakdown keys include `layer1_score`, `layer2_score`, `layer3_score`, `semantic_score`, `tfidf_score`, `keyword_coverage`, `kg_score`, `nlp_score`, `final_score`. |
| 9 | Round transitions and skill rotation | PASS | Rotation observed via API: Python rounds 1-3, React rounds 4-6, SQL rounds 7-9. |
| 10 | Dashboard with Elo chart, per-round breakdown, engagement labels | PASS | Dashboard rendered after proxy fix. Screenshot: `docs/task5_dashboard_breakdown.png`. Dashboard payload includes `engagement_label`, `engagement_confidence`, `engagement_delta`. |
| 11 | Refresh mid-session recovers from localStorage | PASS | Browser quick-start session reloaded on `/interview/...` and recovered the same round/question. Added active-round persistence in `Interview.jsx`. |

## Key Command Evidence

### PDF Upload via Vite Proxy

```json
{
  "skills": [
    "Docker",
    "JavaScript",
    "Machine Learning",
    "MongoDB",
    "Python",
    "REST",
    "React",
    "SQL",
    "System Design"
  ],
  "skill_count": 9,
  "has_candidate": true
}
```

### Session Start

```json
{
  "session_id": "5af73bb5-2c9f-46ab-a652-3a4cc8bb48e5",
  "skills": ["Python", "React", "SQL"],
  "total_rounds": 9,
  "current_skill": "Python",
  "difficulty": "medium"
}
```

### Nine-Round Completion

```text
round 1 final_score=66.68 next_skill=Python session_complete=false
round 2 final_score=66.68 next_skill=Python session_complete=false
round 3 final_score=66.68 next_skill=React session_complete=false
round 4 final_score=66.68 next_skill=React session_complete=false
round 5 final_score=66.68 next_skill=React session_complete=false
round 6 final_score=66.68 next_skill=SQL session_complete=false
round 7 final_score=66.68 next_skill=SQL session_complete=false
round 8 final_score=66.68 next_skill=SQL session_complete=false
round 9 final_score=66.68 next_skill=null session_complete=true
```

### Dashboard Payload Check

```json
{
  "status": "completed",
  "skills": ["Python", "React", "SQL"],
  "completed_rounds": 9,
  "avg": 66.68,
  "first_engagement": {
    "engagement_label": "High",
    "engagement_confidence": 0.76,
    "engagement_delta": 1
  }
}
```

### Server STT

```json
{"text":"Hello from Interviv Server transcription this is a microphone smoke test."}
```

### Build

```text
✓ 2836 modules transformed.
dist/assets/index-CMqlPpXq.js   1,414.74 kB │ gzip: 378.89 kB
✓ built in 2.71s
```

## Fixes Made During Task 5

- Fixed Vite dev proxy conflict: direct `/dashboard/:sessionId` now renders the React dashboard instead of raw backend JSON.
- Updated frontend API requests to use `/api/*` when `VITE_API_BASE_URL` is not set.
- Added `/api` proxy rewrite in `frontend/vite.config.ts`.
- Added active interview state persistence in `Interview.jsx` so refresh recovers the current unanswered round.

## Known Issues / Residual Risk

- The in-app browser cannot automate the OS file picker or set the exact requested 1366x768 viewport. The dashboard and interview were visually checked in the available in-app browser viewport; manual 1366x768 verification is still recommended.
- Camera and microphone permissions are blocked in the in-app browser, so physical webcam calibration, live smile -> High classification, and browser Web Speech recognition could not be proven here. Graceful fallback paths passed.
- `npm run build` warns that the JS bundle is larger than 500 kB after adding face-api.js. This is a performance warning, not a build failure.
- Console warnings observed were React Router future-flag warnings only.

## Screenshots

- Dashboard with scoring breakdown expanded: `docs/task5_dashboard_breakdown.png`
- Camera blocked / calibration skipped smoke: `docs/task4_camera_blocked_skip.png`
