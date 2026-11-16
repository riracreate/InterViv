# interViv Session Handoff

## State
- **Branch**: `ws2-pre-pilot-checkpoint` (local only; no upstream tracking branch; `origin` is `https://github.com/riracreate/InterViv.git`)
- **Latest commit**: updating for `H2` (DB guard path parity with `run_local.py:164` + `samefile` check) after `H1` (`dd060a6`, parked `v4.1` patch)
- **Database**: `local-data/interviv-local.sqlite3` intact (`sha256: 93dfc4b9dd11ae4e974faa069eedd2f877f6f045c1c66cae90a2d61d108f2801`); `DATABASE_URL` is not defined in `.env`. Neither `.env`, `local-data/`, `interviv.db`, nor `data/interViv — Answer Rating (Responses).xlsx` is tracked by git. `scripts/pregenerate_bundles.py` refuses all runs (`--dry-run`, `--estimate`, non-live, `--live`) when `DATABASE_URL` resolves to or `os.path.samefile` matches `local-data/interviv-local.sqlite3`.
- **Parked guard proposal**: The previous working-tree draft is parked at `docs/parked/guard_short_cap_v4_1.patch` (with rationale and `pos=35` note in `docs/parked/README.md`). Working tree `modules/answer_guard_v4.py` (`sha256: 90a77639bb0264cb61e0454f4508e1c5c7d3bae42b025b649d7cba52db2fa1ae`) and `tests/test_scorer_v4.py` are restored to `2bcd3d7`.
- **Default scorer**: `v3` remains default; `v4` sits behind `SCORER_VERSION=v4` and stays OFF (`v1`–`v4` baselines and hash locks untouched).
- **Tests**: Full suite passed (`1148 passed, 6 skipped, 0 failed`).

## Decisions & Known Limitations
- **Scorer feature work stopped**: `word_count` alone achieves `0.89` on `n=50-dev` (partials `0.33–0.40`; Mohler tune gain over semantic alone `+0.013`). No further features, no `v4` changes.
- **Guard `v4.1` parked (not implemented)**: Removing `content_recall < 0.50` changed `0` decisions on Mohler tune and `1` of `50` on `n=50-dev`, and no hyphen/dangling-ending rule is added for `pos=35`. Guard changes wait for the fresh human rating set.
- **Known limitation (Mohler tune 1–2 word reference false positives)**: Short 1–2 word Mohler tune reference answers trigger `v4` guard false positives; interview references are multi-sentence, so this is accepted as a known limitation with no fix.

## Done (Takeover Verification, T1–T4, H1–H2)
- **Takeover Verification (`0a`–`0f`)**: Verified DB hash, full pytest, existing DB guard, diagnostic artifacts (`artifacts/scorer_v4_diagnostics.json` holds `spearman_diff_v4with_minus_blended_all = [-0.0056, 0.0305]`), and `50`-answer band definitions.
- **T1**: Audited `scripts/diagnose_scorer_v4.py` and `scripts/experiment_scorer_features.py` data loads and committed both unchanged (`b64d326`); created `docs/HANDOFF.md` (`b79fc6b`).
- **T2**: Added unconditional path-resolved/symlink-safe `protected_local_db_error()` check to `scripts/pregenerate_bundles.py` (`e52f501`), added temp-path tests in `tests/test_pregenerate_db_guard.py`, ran full pytest (`1147 passed, 6 skipped`), and verified real DB sha256 unchanged.
- **T3**: Measured committed `v4` (`2bcd3d7`) vs uncommitted edited `v4` guard on Mohler tune (`1,484` rows) and `n=50-dev` (never held-out); explained `10.2%` tune vs `2.5%` (`12/482`) held-out FP split from code/existing artifacts; proposed minimal `v4.1` versioning design without implementing.
- **T4**: Added `word_count` and `semantic_score` baselines plus `n=50-dev` partial Spearman controlling for `word_count` to `scripts/experiment_scorer_features.py`; ran on Mohler tune and `n=50-dev` only (`artifacts/scorer_feature_experiment.json`); committed `f2e5f46`.
- **H1**: Saved uncommitted guard diff to `docs/parked/guard_short_cap_v4_1.patch` + `docs/parked/README.md` (`dd060a6`), restored `modules/answer_guard_v4.py` and `tests/test_scorer_v4.py` to `2bcd3d7`, verified `answer_guard_v4.py` sha256 matches `data/baselines/v4/SHA256SUMS.json`, and confirmed full pytest (`1146 passed, 6 skipped`).
- **H2**: Added `os.path.samefile` check to `protected_local_db_error()` in `scripts/pregenerate_bundles.py` and tests verifying `_protected_local_db_path()` equals `scripts/run_local.py:164`'s DB path plus temp-file `samefile` protection in `tests/test_pregenerate_db_guard.py`; confirmed full pytest (`1148 passed, 6 skipped`).

## Next
- **D1**: Write `docs/design/interview_flow.md` (~2 pages, design note only, no implementation).
- **Later (when API credits are added)**: Run the 30-bundle live pilot (`30` bundles + second per-(bundle, concept) human-labeling CSV).
