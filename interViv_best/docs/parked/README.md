# Parked Guard Edit (`v4.1` Candidate)

## Files in this directory
- `guard_short_cap_v4_1.patch`: Parked uncommitted diff from `ws2-pre-pilot-checkpoint` (`modules/answer_guard_v4.py` and `tests/test_scorer_v4.py`) removing the `content_recall < 0.50` exemption so high overlap/recall alone never lifts `too_short`. Apply from repo root (`/Users/.../mega 2 copy`) if/when `v4.1` is opened.

## Minimal `v4.1` Design Proposal (Not Implemented)
`2bcd3d7` (`scorer_version = "v4"`) stays frozen and reproducible against `data/baselines/v4/SHA256SUMS.json` (`modules/answer_guard_v4.py` sha256 `90a77639bb0264cb61e0454f4508e1c5c7d3bae42b025b649d7cba52db2fa1ae`). When guard changes resume after a fresh human set:

1. Create `modules/answer_guard_v4_1.py` exposing `check_answer_quality_v4_1` (applying the parked `too_short` change while importing unchanged helpers from `modules/answer_guard_v4.py` and `modules/answer_guard.py`, leaving `modules/answer_guard_v4.py` byte-identical).
2. Add `"v4.1"` to `SUPPORTED_SCORER_VERSIONS` in `modules/scoring_schema.py:16` (keep `"v3"` default).
3. Update `backend/scoring/pipeline.py:809` to route `current_scorer_version() in ("v4", "v4.1")` to `_run_scoring_pipeline_v4(..., scorer_version=...)` (`backend/scoring/pipeline.py:603`), select `check_answer_quality_v4_1` for `"v4.1"` (`backend/scoring/pipeline.py:615,624`), and stamp `"scorer_version": scorer_version` at `backend/scoring/pipeline.py:739,784`.
4. Add `tests/test_scorer_v4_1.py` and `data/baselines/v4.1/SHA256SUMS.json`.

## Note on `pos=35` (`n=50-dev`)
Even with `guard_short_cap_v4_1.patch` applied, `n=50-dev` `form_position=35` (`row_id=70`, `"ZK-Rollups use validity proofs (zero-knowledge) to."`, `6` whitespace words, 23-rater mean `0.91`) remains uncapped (`reason=None`): `_word_tokens` splits hyphenated words (`zk`, `rollups`, `zero`, `knowledge`), yielding `8` tokens against a `15`-token reference, so both `len(tokens) < 8` and `short_vs_ref` (`8 < 0.5 * 15 = 7.5`) in `answer_guard_v4.py:121-125,143` evaluate `False`. Per reviewer decision, do **not** add a hyphen or dangling-ending rule to fit one dev item; defer guard changes until the fresh human set is collected.
