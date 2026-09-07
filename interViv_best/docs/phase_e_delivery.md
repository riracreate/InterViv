# Phase E delivery — system design + honest AV capability surfaces

## Scope split

### E.1 (shipped)

- First-class **system_design** block category under the Phase B block contract
  (compose/repeat with Verbal, OA, SQL, Interview, Coding).
- Explicit rubric with named criteria; evaluation mode
  `structured_self_assessment` only — **no automatic diagram correctness**.
- Persistence: `system_design_attempts` (Alembic `20260907_0007`), registered in
  `SQLAlchemyDatabase.__getitem__`, full field round-trip.
- AV: capability probe (`GET /av/capabilities`), distinct client states,
  reuse of existing Interview capture + `/transcribe`. Unavailable
  transcription yields retryable failure with **no fabricated transcript** and
  **no speech score**. Speech readiness is not offered.
- Ownership on system-design attempt list/delete. Retention documented below.

### E.2 (blocked — not implemented)

| Item | Blocker |
|------|---------|
| Durable owned video/audio blob pipeline | No LargeBinary/blob store; ffmpeg absent |
| ffmpeg-based media processing | `ffmpeg` not installed |
| Speech fluency / audio readiness scores | Explicitly not offered; would invent signal |
| Automatic diagram correctness | No diagram editor; product forbids auto verdict |
| Device-capture verification claim | Needs real browser + real hardware |
| C.2 live coding execution | Out of Phase E scope |

## Step 0 notes

- Phase C scoring claims re-audited under Phase D Step 0 / E.0; baseline is
  **2/8** on `scripts/scoring_regression.py` (not 4/8).
- Localhost bind works on this host.
- Existing voice/transcription: `backend/routes/transcribe.py` + Interview
  MediaRecorder / SpeechRecognition. faster-whisper tiny.en cache may be
  present under `~/.cache/huggingface/hub`.

## Evaluation boundary (user-visible)

System-design scores reflect **structured self-assessment** against named
rubric criteria. Incomplete ratings produce **no score** (not a zero). Diagrams
and component lists are **not** auto-validated.

## AV retention and deletion

- E.1 does **not** persist audio or video blobs.
- `/transcribe` writes a temporary upload, processes it, and deletes the file.
- System-design attempts are owned by the submitting user and deletable via
  `DELETE /av/system-design-attempts/{id}`.
- Artifact paths, storage keys, and raw blobs are never returned in catalogs,
  resume, dashboards, review, or error messages (none are stored for AV).

## Concerns (real vs not)

1. **Device capture** — real in browser when permission/hardware allow; states
   are distinct. Hardware verification is NOT VERIFIED in CI.
2. **Transcription** — real when faster-whisper + local cache work; otherwise
   `service_unavailable` (503), no transcript invented.
3. **Interview interaction** — real (existing Interview engine; system-design
   uses the same session/answer path).
4. **Feedback** — text/self-assessment only; no speech score.

## Commands to verify

```
cd interViv_best
python -m pytest tests/ -q
cd frontend && npm test && npm run build
python scripts/scoring_regression.py
alembic heads
git diff --check
```
