# interViv Session Handoff

## State
- **Branch**: `ws2-pre-pilot-checkpoint` (local only; no upstream tracking branch; `origin` is `https://github.com/riracreate/InterViv.git`)
- **Latest commit**: `b64d326` (`chore(ws3): commit existing v4 diagnostic and bounded experiment scripts unchanged`)
- **Database**: `local-data/interviv-local.sqlite3` intact (`sha256: 93dfc4b9dd11ae4e974faa069eedd2f877f6f045c1c66cae90a2d61d108f2801`); `DATABASE_URL` is not defined in `.env`. Neither `.env`, `local-data/`, `interviv.db`, nor `data/interViv — Answer Rating (Responses).xlsx` is tracked by git.
- **Uncommitted working-tree edits (kept uncommitted until review)**:
  - `modules/answer_guard_v4.py` (Queue #1 draft: removes `content_recall < 0.50` exemption on short answers so similarity/recall alone never lifts `too_short`)
  - `tests/test_scorer_v4.py` (adds `test_guard_v4_similarity_alone_does_not_lift_short_cap`)
- **Default scorer**: `v3` remains default; `v4` sits behind `SCORER_VERSION=v4` and stays OFF (`v1`–`v3` baselines and hash locks untouched).
- **Tests**: Full suite passed before T1 (`1146 passed, 6 skipped, 0 failed`).

## Done (Takeover Verification & T1)
- Completed read-only repo takeover verification (`0a`–`0f`): confirmed DB hash, full pytest suite (`1146` pass / `6` skip), existing `pregenerate_bundles.py` in-memory DB guard, stored diagnostic artifacts (`artifacts/scorer_v4_diagnostics.json` holds `spearman_diff_v4with_minus_blended_all = [-0.0056, 0.0305]`), and `50`-answer band definitions (23-rater mean defines `Poor 0–30 / Average 31–60 / Good 61–100` score bands; dataset `label` defines sampling stratification `20 Poor / 15 Average / 15 Good`).
- Audited `scripts/diagnose_scorer_v4.py` and `scripts/experiment_scorer_features.py` data loads and committed both unchanged (`b64d326`).
- Created `docs/HANDOFF.md` (`T1`).

## Next
- **T2**: Add strict DB guard in `scripts/pregenerate_bundles.py` refusing `local-data/interviv-local.sqlite3` (via resolved absolute path / symlink check, no env override, all modes), test with temp path, run full pytest, verify real DB sha256, and commit.
- **T3**: Measure guard edit (`v3`/committed `v4`/edited `v4`) on Mohler tune and `n=50-dev` (never held-out), explain `10.2%` tune vs `2.1%`/`2.5%` held-out from existing code/artifacts, propose smallest `v4.1` versioning design without implementing yet, and leave guard edit uncommitted.
- **T4**: Add word-count, semantic, and partial-Spearman (controlling for word count on `n=50-dev`) columns to `scripts/experiment_scorer_features.py`, run on Mohler tune and `n=50-dev` only, report table, and commit script.
- **Later (next sessions)**: Design staged interview flow; run 30-bundle live pilot once API credits are added.
