# interViv Session Handoff

## State
- **Branch**: `ws2-pre-pilot-checkpoint` (local only; no upstream tracking branch; `origin` is `https://github.com/riracreate/InterViv.git`)
- **Latest commit**: updating for `T4` (`scripts/experiment_scorer_features.py` bounded experiment + `HANDOFF.md`)
- **Database**: `local-data/interviv-local.sqlite3` intact (`sha256: 93dfc4b9dd11ae4e974faa069eedd2f877f6f045c1c66cae90a2d61d108f2801`); `DATABASE_URL` is not defined in `.env`. Neither `.env`, `local-data/`, `interviv.db`, nor `data/interViv — Answer Rating (Responses).xlsx` is tracked by git. `scripts/pregenerate_bundles.py` refuses all runs (`--dry-run`, `--estimate`, non-live, `--live`) when `DATABASE_URL` resolves to `local-data/interviv-local.sqlite3`.
- **Uncommitted working-tree edits (kept uncommitted until review)**:
  - `modules/answer_guard_v4.py` (Queue #1 draft: removes `content_recall < 0.50` exemption on short answers so similarity/recall alone never lifts `too_short`)
  - `tests/test_scorer_v4.py` (adds `test_guard_v4_similarity_alone_does_not_lift_short_cap`)
- **Default scorer**: `v3` remains default; `v4` sits behind `SCORER_VERSION=v4` and stays OFF (`v1`–`v3` baselines and hash locks untouched).
- **Tests**: Full suite passed after T2 (`1147 passed, 6 skipped, 0 failed`); re-verifying after T4.

## Done (Takeover Verification, T1–T4)
- **Takeover Verification (`0a`–`0f`)**: Verified DB hash, full pytest, existing DB guard, diagnostic artifacts (`artifacts/scorer_v4_diagnostics.json` holds `spearman_diff_v4with_minus_blended_all = [-0.0056, 0.0305]`), and `50`-answer band definitions.
- **T1**: Audited `scripts/diagnose_scorer_v4.py` and `scripts/experiment_scorer_features.py` data loads and committed both unchanged (`b64d326`); created `docs/HANDOFF.md` (`b79fc6b`).
- **T2**: Added unconditional path-resolved/symlink-safe `protected_local_db_error()` check to `scripts/pregenerate_bundles.py` (`e52f501`), added temp-path tests in `tests/test_pregenerate_db_guard.py`, ran full pytest (`1147 passed, 6 skipped`), and verified real DB sha256 unchanged.
- **T3**: Measured committed `v4` (`2bcd3d7`) vs uncommitted edited `v4` guard on Mohler tune (`1,484` rows) and `n=50-dev` (never held-out); explained `10.2%` tune vs `2.1%`/`2.5%` held-out FP split from code/existing artifacts; proposed minimal `v4.1` versioning design without implementing yet; left guard edit uncommitted.
- **T4**: Added `word_count` and `semantic_score` baselines plus `n=50-dev` partial Spearman controlling for `word_count` to `scripts/experiment_scorer_features.py`; ran on Mohler tune and `n=50-dev` only (output written to `artifacts/scorer_feature_experiment.json`); committed updated script without changing `v4`.

## Next
- Wait for reviewer decision on **T3** (`v4.1` proposal and remaining `pos=35` 8-token fragment edge case) and **T4** (feature experiment stop-rule judgment).
- Next session: design note for the staged interview flow; run 30-bundle live pilot once API credits are added.
- **T4**: Add word-count, semantic, and partial-Spearman (controlling for word count on `n=50-dev`) columns to `scripts/experiment_scorer_features.py`, run on Mohler tune and `n=50-dev` only, report table, and commit script.
- **Later (next sessions)**: Design staged interview flow; run 30-bundle live pilot once API credits are added.
