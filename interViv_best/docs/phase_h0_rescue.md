# Phase H.0 — rescue of at-risk phase21 objects

No product changes. No merge into any active branch. No checkout of the
`phase21-verbal-ability` worktree.

## Why this was urgent

Phase G found uncommitted Verbal UI work surviving only as **unreferenced**
Git objects. Unreferenced objects are eligible for `git gc` / auto-gc and can
disappear permanently after ordinary repository maintenance.

## Session protections

| Action | Detail |
|--------|--------|
| `gc.auto` prior | **unset** (local) |
| Set for session | `git config --local gc.auto 0` in worktree `phase-b-block-practice` |
| Restored | at end of Phase H (see H.1 / final audit) — prior was unset → `git config --local --unset gc.auto` |
| Not run | `git gc`, `git prune`, `git repack` |
| phase21 worktree | left untouched; still clean at `fe75a32` |

## Rescue refs created

These refs add **reachability only**. They do not move `codex/phase-b-block-practice`,
`phase21-verbal-ability`, or `fe75a32`.

| Ref | Object | Type | Size (bytes) |
|-----|--------|------|--------------|
| `refs/rescue/phase21-verbal-ui` | `381c7841c62c65fafec62c0a4b03b4abc5534c83` | commit | 246 |
| `refs/rescue/phase21-blob-65bf858a` | `65bf858acb49281e10b42410a952293b0c2c4490` | blob | 25825 |
| `refs/rescue/phase21-blob-8405effd` | `8405effdaaa1004b2753686df24dac813478011c` | blob | 50308 |
| `refs/rescue/phase21-blob-06bc5daf` | `06bc5daf6d26cfced8744eb829d5350fc39d0b5f` | blob | 3654 |

### fsck confirmation

After creating the refs, `git fsck --lost-found` **no longer lists** any of the
four SHAs as dangling. (Other unrelated dangling objects remain in the shared
store; they were not part of this rescue.)

## What each object is

### Blobs (the Verbal UI work Phase G meant)

These three blobs are **one coherent uncommitted snapshot** of interview/UI
fixes on top of `fe75a32` (phase21 tip). They are **not** contained in dangling
commit `381c7841`.

| Blob | Appears to be | Relation to `fe75a32` | Relation to current chain (`65a456e`) |
|------|---------------|----------------------|--------------------------------------|
| `65bf858a…` | `interViv_best/frontend/src/pages/Upload.jsx` | ~10 line delta vs `fe75a32` Upload: adds `isCheckingAuth`, Verbal entry button auth-aware labels, login navigate | Current Upload (`975c3ab7…`) diverged: Phase D target/resume carry-forward; **no** Verbal Ability practice entry |
| `8405effd…` | `interViv_best/frontend/src/pages/Interview.jsx` | ~19 line delta vs `fe75a32` Interview: `usesInterviewMedia` gates mic/camera/calibration to `technical_short_answer` only | Current Interview (`836055d9…`) is a much later tree (blocks, AV states, SD, scoring-mode UI). Naïve apply would conflict |
| `06bc5daf…` | frontend node:test render suite | Asserts Verbal MCQ opens without camera calibration; technical retains calibration | No equivalent file on the B–G chain under that exact content |

**Same work?** Yes for the three blobs: one WIP set (Upload entry + media gate + test).
**Same as commit `381c7841`?** **No.**

### Dangling commit `381c7841` (different work)

```
docs: keep keyword stuffing task diagnosis-only
author pneet <student@gamil.com>
date   Wed Aug 26 19:20:33 2026 +0530
parent 523e6c80eda835fcaa2d0b417043265e116a10a3
```

Its tree includes `Upload.jsx` blob `848b18bc…` and `Interview.jsx` blob
`6af568c0…` — **different SHAs** from the rescued Verbal UI blobs. The commit
message and tree (includes `.interviv_model_lab_runtime` copies, older alembic,
etc.) are unrelated to the Verbal entry WIP. It was listed in Phase G as a
dangling commit found during the same `fsck` sweep; it is rescued for
reachability, but it is **not** a snapshot of the three Verbal UI blobs.

## How to inspect (read-only)

```bash
git show refs/rescue/phase21-blob-65bf858a
git show refs/rescue/phase21-blob-8405effd
git show refs/rescue/phase21-blob-06bc5daf
git log -1 --stat refs/rescue/phase21-verbal-ui
```

Do **not** merge, cherry-pick, or check these into product branches without a
scheduled integration phase. See `docs/phase_g_delivery.md` Verbal UI gap and
`docs/review_guide.md`.

## Objects already unrecoverable?

None of the four named objects were missing at rescue time. All four
`git cat-file -t` succeeded before `update-ref`.
