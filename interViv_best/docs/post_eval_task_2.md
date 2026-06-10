# Post-Eval Task 2 — Server-Side STT

Status: completed

## What changed

- Added `faster-whisper>=1.0.0` to `requirements.txt`.
- Added `POST /transcribe` in `backend/routes/transcribe.py`.
- Registered the route in `backend/main.py`.
- Added `transcribeAudio()` in `frontend/src/lib/api.js`.
- Added a MediaRecorder-based server transcription path in `frontend/src/pages/Interview.jsx`.

## Verified

- Backend route registration: `['/transcribe']`
- Curl smoke test returned:

```json
{"text":"Hello from Interviv Server transcription this is a microphone smoke test."}
```

- Frontend production build completed successfully.
- Backend Python files compiled successfully.

## Graceful Degradation

- Browser STT supported: user can keep browser speech recognition or enable server transcription.
- Browser STT unsupported: server transcription is selected by default and the mic button shows `Record (server)`.
- Transcription unavailable: UI shows `Transcription unavailable, please type your answer`.
- Mic unavailable: typed-answer mode remains usable.
