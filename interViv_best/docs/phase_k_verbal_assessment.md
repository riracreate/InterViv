# Phase K — rescued phase21 Verbal UI vs current chain

**Read-only assessment. No integration.**
**Branch tip assessed:** `dac9c3c` (Phase J). **Chain root:** `0442493` (A).
**Rescue refs inspected (unchanged):** `refs/rescue/phase21-blob-*`, `refs/rescue/phase21-verbal-ui`.
**Origin worktree:** `phase21-verbal-ability` @ `fe75a32` — read-only; not checked out or modified.

Scratch extracts used for inspection lived **outside** the repository (`/tmp/phasek_verbal_scratch_*`). No rescued bytes were applied to product source.

---

## Step 0 — inventory of the snapshot

### Blob `65bf858a…` (25 825 B) — Upload.jsx WIP

| Field | Value |
|-------|--------|
| Path in phase21 tree | `interViv_best/frontend/src/pages/Upload.jsx` |
| Role | Landing / resume-upload page; adds a **standalone Verbal Ability practice** entry |
| Completeness | **Mid-edit but coherent.** Small delta (~10 lines) on top of `fe75a32` Upload. Not a half-finished syntax break; the Verbal button and auth-checking state are finished enough to run. |

**Function (plain):** While checking auth (`isCheckingAuth`), the page can navigate unauthenticated users toward login for Verbal practice. When ready, a `data-testid="verbal-practice-entry"` button starts Verbal Ability practice via the existing start helper (`startVerbalPractice`), with labels that flip between “Checking sign-in…”, “Sign in for…”, and “Verbal Ability practice”.

**Depends on:** React Router (`navigate`), local auth check pattern already on that Upload tree, Verbal start payload helpers from the fe75a32-era frontend, existing session-start API, page styles already on Upload.

### Blob `8405effd…` (50 308 B) — Interview.jsx with `usesInterviewMedia`

| Field | Value |
|-------|--------|
| Path in phase21 tree | `interViv_best/frontend/src/pages/Interview.jsx` |
| Role | Live interview shell; gates mic / camera / face-api / calibration to technical rounds only |
| Completeness | **Complete relative to fe75a32 Interview.** ~19-line conceptual delta (`usesInterviewMedia`). Not mid-syntax. Still an **older product surface** than the B–J Interview (no E.1 AV panel, no answer drafts, weaker multi-round coverage vs current). |

**Function (plain):** Introduces
`const usesInterviewMedia = roundType === 'technical_short_answer'`.
That flag gates: loading engagement models, wiring `SpeechRecognition`, starting the camera, showing the calibration screen, running engagement classification during the round, and showing the technical per-round timer chrome. MCQ (Verbal) therefore opens straight into the MCQ UI without calibration / camera permission theatre.

**Depends on:** `../lib/engagement` (`loadModels`, `classifyFrame`, …), existing MCQ/SQL round components of that era, `getUserMedia` / `MediaRecorder` / `SpeechRecognition`, interview state helpers, calibration UI already in that file. Does **not** depend on `fetchAvCapabilities`, `AvUnavailablePanel`, or `AV_STATES` (those arrived later in E.1).

### Blob `06bc5daf…` (3 654 B) — Verbal MCQ render test

| Field | Value |
|-------|--------|
| Intended path | Frontend node:test suite (render-to-static-markup of `Interview.jsx`); **not** the committed `fe75a32` file `frontend/tests/verbalPractice.test.js` |
| Role | Assert Verbal MCQ skips camera calibration; technical retains it |
| Completeness | **Complete as a WIP test.** Bundles Interview via esbuild with an engagement stub; two tests. |

**Function (plain):** SSR-renders Interview with `round_type: 'mcq'` and expects `mcq-round-container`, stem text, MCQ duration `20:00`, and **no** Calibration / `<video` / technical “Time left in this round” / `02:00`. Second test: technical still shows Calibration (uncalibrated) and textarea + round timer when calibrated.

**Depends on:** `esbuild`, `react-dom/server`, `react-router-dom`, Interview.jsx + engagement stub plugin. **Differs** from committed `verbalPractice.test.js` on `fe75a32` (that file only checks payload helpers / `VERBAL_PRACTICE_CONFIG` — different MD5; not this blob).

### Phase H claims — confirmed

1. **The three blobs are one coherent Verbal UI snapshot on `fe75a32`.**
   Evidence: Upload vs `fe75a32` Upload is a ~10-line auth + Verbal-entry delta (`diffstat`: 6 insertions / 4 deletions). Interview vs `fe75a32` Interview is the `usesInterviewMedia` gate (~95 unified-diff lines, small conceptual change). The render test asserts exactly that Interview behaviour. Same WIP theme: Verbal entry + media gate + regression test.

2. **Commit `381c7841` (`refs/rescue/phase21-verbal-ui`) is unrelated docs work.**
   Evidence: message `docs: keep keyword stuffing task diagnosis-only`. Its tree’s Upload / Interview blobs are `848b18bc…` and `6af568c0…` — **different SHAs and MD5s** from the rescued Verbal UI blobs (`65bf858a…` / `8405effd…`). It does not contain the three WIP files.

---

## Step 1 — compare against the current chain (`dac9c3c`)

### (a) Interview.jsx — **divergent** (most important)

| | Rescued (`8405effd`) | Current chain |
|--|----------------------|---------------|
| Size | 50 308 B | 58 050 B |
| Media gate | `usesInterviewMedia` early-exits models, STT setup, camera, calibration | **No** `usesInterviewMedia`. Models / SpeechRecognition / camera effects still run regardless of round type. `showCalibrationScreen` does **not** require `technical_short_answer` |
| AV honesty (E.1) | Absent | `fetchAvCapabilities`, `AvUnavailablePanel`, `AV_STATES`, classified media errors |
| Capture / STT | MediaRecorder + `/transcribe` path of that era | Same family, plus explicit capability probe and unavailable UI |
| Drafts (Phase B) | Absent | `fetchAnswerDraft` / `saveAnswerDraft` gated to technical |
| Round types | MCQ / SQL (+ limited support messaging) | MCQ, SQL, coding, system_design, technical — richer shell |

**What `usesInterviewMedia` does:** Boolean “this round needs interview media.” Only `technical_short_answer` is true. Everything that would request camera/mic models or show calibration is skipped for Verbal MCQ (and other non-technical types on that tree).

**Relation to E.1 AV:** **Competing bases, complementary intent.**

- E.1 answers: “When media **is** needed, how do we tell the truth about permission / device / transcription availability?”
- Rescued gating answers: “When media is **not** needed (Verbal MCQ), do not enter that path at all.”

They are **not** the same solution. Dropping the rescued Interview over the current file would **lose** E.1 honesty, Phase B drafts, coding / system-design round shells, and later scoring-mode UI. Dropping nothing keeps a **real gap**: current Verbal / MCQ can still load face-api, spin up recognition, and hit calibration when `isVideoOn` defaults true — behaviour the rescued test was written to forbid.

| Capability | Rescued | Current |
|------------|---------|---------|
| Skip camera/calibration for MCQ | Yes (`usesInterviewMedia`) | **No** (gap) |
| `GET /av/capabilities` + unavailable panel | No | Yes |
| Distinct AV states | No | Yes |
| Answer draft restore/autosave | No | Yes |
| System design / coding round UI | Weak / absent vs current | Yes |
| MediaRecorder → `transcribeAudio` | Yes (older wiring) | Yes (plus capability gate) |

**Verdict:** **Divergent.** Chain is **ahead** on AV honesty and multi-mode Interview product. Chain is **behind** on round-type media gating. Full-file integration is a **merge with real conflicts**, not a graft.

### (b) Upload.jsx — **divergent**

| | Rescued | Current chain |
|--|---------|---------------|
| Verbal entry on Upload | Yes (`verbal-practice-entry`) | **No** (grep: no Verbal on Upload) |
| Auth-checking UX for that entry | Yes | N/A |
| Phase D target / resume carry-forward | No (fe75a32-era Upload) | Yes |
| Where Verbal actually starts today | Would be Upload | **Practice Hub** (`Practice.jsx` mode `verbal`, builder Verbal blocks) — browser-verified in Phase F |

**Does the chain have an Upload Verbal entry?** No.
**Is the product missing a Verbal start path?** No — Practice Hub covers standalone Verbal and mixed builder Verbal blocks (Phase F VERIFIED journeys).

To make the rescued Upload work against the **current** API / block contract / routing it would need re-basing onto current Upload (target/resume), and its start helper must emit the **block-contract** Verbal payload the B–J backend expects — not assume fe75a32-only start shapes. That is adaptation work, not a blob checkout.

**Verdict:** **Divergent.** Chain Upload is **ahead** on Phase D. Chain is **behind** only on a duplicate entry point whose job is already done on Practice.

### (c) Verbal MCQ render test — **behind** (chain)

Current `frontend/tests/` has `avStates`, `roundContract`, `blockBuilder`, `practiceBuilder`, etc. **No** suite SSR-renders Interview to assert “MCQ opens without Calibration / video.” Closest Verbal coverage is payload / builder contract tests, not Interview chrome.

The rescued test asserts behaviour the chain **does not currently lock**: MCQ must not show calibration or technical timer chrome.

**Verdict:** Chain is **behind** on this assertion. The rescued file is still meaningful **if** (and after) Interview gains equivalent gating; as-is it would fail against current Interview.

---

## Step 2 — integration cost (assessment, not a plan)

### What integrating each file would touch

| Rescued piece | Would touch (by name) |
|---------------|------------------------|
| Interview media gate (idea or file) | `frontend/src/pages/Interview.jsx` (primary); possibly `frontend/src/lib/engagement.js` call sites only via Interview; new or updated test under `frontend/tests/` |
| Upload Verbal entry | `frontend/src/pages/Upload.jsx`; likely `frontend/src/lib/practiceBuilder.js` / start helpers; auth redirect tests; Practice vs Upload product copy |
| Render test | New `frontend/tests/…` file; esbuild + SSR harness; depends on Interview behaviour first |

### Genuine conflicts

- **Interview.jsx is the conflict.** ~515 lines of unified diff between rescued and current; symbols disjoint (`usesInterviewMedia` vs `fetchAvCapabilities` / `AvUnavailablePanel` / drafts / SD / coding). A naïve blob replace destroys E.1 and B–J Interview work. A port must **re-implement the gate inside the current file**, not restore `8405effd`.
- Upload: conflict with Phase D resume/target if someone tries to restore `65bf858a` wholesale; Verbal button itself is additive but redundant with Practice.

### Re-verification blast radius (existing records)

Any Interview / Verbal / AV change should re-hit journeys already tabulated in:

- `docs/phase_f_delivery.md` — Verbal standalone; mixed Verbal→Interview→SQL; Progress measured Verbal; `/av/capabilities` partial; AV UI states still blocked for exhaustive tour.
- `docs/phase_e_delivery.md` — AV capability probe, unavailable surfaces, no fabricated speech scores; Interview interaction.
- `docs/phase_g_delivery.md` / `docs/review_guide.md` — browser checklist (Learn, Progress SD Not measured, builder, double-submit); rescue refs note.
- Frontend: `avStates.test.js`, Interview-adjacent round/builder tests; full `npm test` + production build.
- Backend: full `pytest`; scoring_regression modes per baseline note (unchanged by this docs phase).

Blast radius is **every browser journey that opens Interview**, plus Verbal start from Hub (and Upload if that entry is added), plus AV permission/device paths on technical rounds.

### What can move independently vs together

| Take alone? | Item |
|-------------|------|
| Yes (concept) | `usesInterviewMedia`-style gate **ported** into current Interview |
| Yes (after gate) | Render test asserting MCQ skips calibration |
| Yes but low value | Upload Verbal button (product already covered on Practice) |
| No | Whole rescued `Interview.jsx` as a replacement |
| No | Commit `381c7841` (unrelated) |
| Must move with gate | Any test that encodes the gate; otherwise the test fails or lies |

### Obsolete?

- **Whole-file Interview.jsx from rescue:** effectively obsolete as a drop-in; superseded by B–J Interview + E.1.
- **`usesInterviewMedia` idea:** **not** obsolete; chain never absorbed it.
- **Upload Verbal entry:** largely **product-obsolete** given Practice Hub; may still matter if the owner wants Upload as a second front door.
- **Render test:** not obsolete; chain lacks the assertion.
- **`381c7841`:** not Verbal UI; leave as rescue-only history.

### Difficulty (honest)

| Scope | Estimate | Why |
|-------|----------|-----|
| Port media gate into current Interview + add render test | **Medium** | Localized boolean + effect guards, but Interview is dense and AV/calibration interactions must not regress technical rounds |
| Also add Upload Verbal entry | **Medium+** | Rebase onto Phase D Upload + align start payload with block contract; duplicate UX to maintain |
| Replace Interview with rescued blob | **Hard / wrong** | Loses E.1, drafts, SD, coding; conflicts everywhere |
| Do nothing | **None now** | Leaves MCQ media/calibration gap unfixed |

---

## Step 3 — recommendation

**Recommend: integrate selectively.**

1. **Do integrate (later authorized phase):** the **`usesInterviewMedia` behaviour** (or equivalent round-type guards) into **current** `Interview.jsx`, plus a render/regression test in the spirit of `06bc5daf`. Keep E.1 AV surfaces for technical rounds.
2. **Do not integrate as files:** drop-in `8405effd` Interview or `65bf858a` Upload.
3. **Upload Verbal entry:** optional / owner call; **default skip** — Practice Hub already provides Verbal start (Phase F verified).
4. **Ignore for product:** `381c7841`.

**Strongest argument against this recommendation:** Selective port still touches the hottest UI file on the chain. If browser evidence already shows Verbal MCQ “just works” without painful calibration in real use (e.g. calibration auto-skips when camera fails), the owner may prefer **do not integrate** and avoid Interview risk until a dedicated UX bug is filed. The counter to that counter: `showCalibrationScreen` is not round-type-gated today, and the rescued test exists precisely because that was considered a product defect on phase21.

### Owner decision (explicit)

This is **the owner’s decision**. The rescued work is **theirs** (phase21 WIP, rescued in H for reachability only). They specifically need to weigh:

- **Interview conflict:** only one lineage can own media behaviour. Keeping chain E.1 **and** adopting their gate means a **port**, not restoring their file. Restoring their file **deletes** E.1 honesty UI.
- **Upload entry:** whether a second Verbal door on Upload is worth maintaining beside Practice Hub.
- **Whether the MCQ calibration/camera gap is still felt in product** — that decides priority vs “leave rescue refs cold.”

---

## Phase L follow-up — gate closed (2026-09-07)

**Defect was live.** Browser Step 0 on disposable DB (`/tmp/interviv_phasel_disposable.db`, `:18000`): Verbal and OA opened MCQ without a Calibration chrome (auto-skip on `NotAllowedError`), but **`getUserMedia` was still invoked** (video constraints, spy count 2). Technical Interview likewise requested media and showed E.1 `AvUnavailablePanel`. So the Phase K counter-argument (gate redundant) was wrong for media setup; the calibration *screen* was environment-masked, the permission request was not.

**Implemented (port, not blob):** `blockUsesInterviewMedia(block_category, round_type)` in current `Interview.jsx` — Verbal/OA skip camera, SpeechRecognition wiring, face-api load, and calibration; other categories keep today’s media path including E.1 AV. Mixed Verbal→Interview resets calibration when entering an interview category. Plumbed `block_category` through Practice/Learn/Problems/Jobs/Coach/Upload navigate state. SSR suite `frontend/tests/interviewMediaGate.test.js` pins Verbal/OA skip, technical keep, and mixed round>1 calibration. Upload Verbal entry and rescued file replace were **not** done.

**Not done:** C.2, E.2, Upload Verbal entry, touching `refs/rescue/*` or the phase21 worktree.

---

## Phase K process attestation

| Check | Result |
|-------|--------|
| phase21 worktree touched | **No** (status left clean @ `fe75a32`) |
| Rescued code merged / cherry-picked / applied to chain | **No** |
| `refs/rescue/*` still reachable | **Yes** (verified at assessment time) |
| Product source edited this phase | **No** — docs only |
| C.2 / E.2 started | **No** |
| Migration needed | **No** (Alembic head remains `20260907_0008`) |

Baseline reminder (unchanged by this phase): scoring_regression 2/8 full, 4/8 degraded; always-present pair gibberish / keyword_stuffing; `human_baseline_report.md` committed form 230 lines, MD5 `5421f9f0fd6efad395666c545e5cf76a`.

## Phase Z follow-up on the L media gate

Z observed OA screens without media chrome/prompts, but the automated browser did not have a proven working grant. Verbal/OA under granted permission and mixed Verbal → Interview remain **PARTIAL / STILL BLOCKED** respectively (Z #18–19). Owner manual capture proof applies to an interview, not those gate scenarios. See [Phase Z](phase_z_browser_verification.md); do not infer closure from source/tests.
