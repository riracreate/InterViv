# Phase M — transcription offline check (incomplete)

**Status:** Incomplete phase. **No Phase M product commit** is on `codex/phase-b-block-practice`.
This document was written in **Phase S** to preserve findings that otherwise lived only in a session that may be gone.

**Attribution:** Items below are **as reported by the Phase M session**, unless a Phase S spot-check is explicitly marked. Phase S did **not** re-run transcription load tests or browser AV verification.

**Chain context:** Between Phase L (`8466c48`) and Phase N (`0d5fd54`). Disposable stack was reported on `127.0.0.1:18000` / `127.0.0.1:5173`. Those ports may still be held awaiting an owner browser permission prompt — later phases were instructed not to disturb them.

---

## What Step 0 established (reported)

| Claim | Source |
|-------|--------|
| Transcription uses `faster_whisper.WhisperModel("tiny.en")`, Hub id `Systran/faster-whisper-tiny.en` | Phase M session report |
| Weights cached under `~/.cache/huggingface/hub/models--Systran--faster-whisper-tiny.en`, about **74 MB** total; `model.bin` about **72 MB**; loads under `HF_HUB_OFFLINE=1` in about **5 s** | Phase M session report |
| With an **empty disposable `HF_HOME`**, load fails loudly with `LocalEntryNotFoundError`, mapped by the route to **503** `transcription_unavailable` | Phase M session report |
| Pattern is **fail-loud**, not SemanticScorer-style silent degrade | Phase M session report (also cited in later docs §e2) |
| Phase J Hub-offline defaults introduced **no warm-cache regression** for this path; a cold machine gets an honest 503 rather than a silently disabled path | Phase M session report |

### Phase S spot-check (cache only; cache not modified)

| Check | Result |
|-------|--------|
| Directory still present | **Yes** — `/tmp/interviv-publish/.cache/huggingface/hub/models--Systran--faster-whisper-tiny.en` |
| `du -sh` size | **74M** |
| `model.bin` blob size | **75537502** bytes (~72.0 MiB) via snapshots → blobs symlink |

Load-time “~5 s under `HF_HUB_OFFLINE=1`” and the cold-`HF_HOME` → 503 mapping were **not** re-executed in Phase S (reported-but-unverified beyond the cache presence/size check).

---

## Browser / AV work that was planned and never finished

All remain **STILL BLOCKED** pending the owner at a browser (permission prompt):

1. Calibration rendered for the first time (owner Allow camera/mic)
2. The seven AV unavailable / capability states in live UI
3. Transcription with **real** audio
4. Recorded-media retention

Phase M did not close live mic/camera verification.

---

## Still unexercised on this chain (cross-phase)

- **Calibration UI has still never rendered** as a completed flow: Phase L established Interview media requests auto-skip on `NotAllowedError` for gated categories; without an Allow, calibration does not appear as a successful gate. Recorded here so it is not mistaken for Phase M completion.
- **E.1’s transcription path has never processed real audio** on this chain — code exists; end-to-end audio → transcript was not observed.

---

## What this document is not

- Not a claim that Phase M finished.
- Not authorization to disturb `:18000` / `:5173`.
- Not a substitute for E.2 (durable AV artifacts) or a live coding runner.

Pointer from the review package: `docs/review_guide.md` §f / §i / §e2.
