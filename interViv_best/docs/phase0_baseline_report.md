# Phase 0 baseline capture — unify-shell `6659fed`

Captured: 2026-09-13T10:58:14Z (scoring_regression finish).
Worktree: `/tmp/interviv-publish/Downloads/mega 2 copy/.worktrees/cursor-ai-design-phase0`
Branch: `phase0/cursor-ai-design` (created from `codex/unify-shell`)
Source commit: `6659feda31b2f27d687f609d59e397911285a6ff`

This report freezes the starting scorer and established-suite evidence **before**
Phase B ports and Phase 0 UI/data fixes. It is not a claim that historical
published figures were reproduced.

## Environment

| Item | Value |
| --- | --- |
| Python | 3.12.4 (venv symlinked from `.worktrees/coding-practice/interViv_best/.venv`) |
| Node | v22.16.0 |
| sklearn / torch / sentence-transformers | 1.8.0 / 2.11.0 / 5.4.1 |
| Platform | macOS 26.6.2 arm64 |
| Worktree `.env` | absent |
| `LENGTH_RATIO_MULTIPLIER_ENABLED` | **off** (env unset; `get_settings().length_ratio_multiplier_enabled` is False) |
| Semantic runtime | **full** (probe cosine 1.0 on identical strings; `fallback_reason` None) |
| MiniLM | `sentence-transformers/all-MiniLM-L6-v2`, hub `refs/main` = `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` |
| `HF_HUB_OFFLINE` / `TRANSFORMERS_OFFLINE` | 1 (runtime_env default) |
| `LLM_LIVE_FETCH` / `JOBS_LIVE_FETCH` | 0 |
| Question-generation env | unset; code default mode is `llm`, but live fetch remains off |

Flags were recorded, not changed.

## Scoring assets

See `data/baselines/v1/SHA256SUMS.json` and `data/baselines/v1/runtime_manifest.json`.

Classifier `modules/answer_quality_lr.joblib` sha256
`2897c8cc6283cbdb4815a78182188ea60c17b39876feefa2d67919f065f16dd7`
matches `modules/model_metadata.json` `artifact_sha256` and the grader-lab
record. Dataset `data/ml_training_data.csv` sha256
`73cd98ef096a3e7a2808da1f66427c79d596531c9084a558e192dc04938fd104`
matches the metadata `dataset_hash`.

Protected scoring paths were hashed as they exist at `6659fed`. They were not
edited for this capture.

## Established suites (run once, before ports)

### `python -m pytest tests/ -q`

```
546 passed, 1 skipped, 54 warnings in 126.03s (0:02:06)
```

Exit 0. The skip is the existing semantic-model marker path. Warnings are
Starlette HTTP_422 deprecation and Alembic `path_separator` notices.

### `python scripts/scoring_regression.py`

```
Running 8 regression case(s)...

case                     final            band                       guard  status
----------------------------------------------------------------------------------
excellent                91.39     [  70, 100]                    -/(none)  PASS
paraphrase               49.62     [  45, 100]                    -/(none)  PASS
partial                  56.10     [  30,  70]                    -/(none)  PASS
empty                     5.00     [   0,  10]                 empty/empty  PASS
gibberish                 6.06     [   0,  25]        repetition/gibberish  FAIL
excessive_repetition      8.40     [   0,  30]       repetition/repetition  PASS
keyword_stuffing         10.00     [   0,  40]  gibberish/keyword_stuffing  FAIL
off_topic                12.50     [   0,  35]         off_topic/off_topic  PASS

FAIL gibberish:
   - guard_applied='repetition', expected 'gibberish'
FAIL keyword_stuffing:
   - guard_applied='gibberish', expected 'keyword_stuffing'

2/8 case(s) failed.
```

Exit 1. These two guard-label mismatches are **pre-existing** on unify-shell
(also recorded on the Phase B branch's delivery note). Scores stay inside the
numeric bands. They are frozen as observed in
`tests/fixtures/scorer_v1_baseline.json`. This capture does not retune guards.

### `npm test` in `frontend/`

```
# tests 55
# pass 54
# fail 1
```

The failure is `frontend/tests/interviewMediaGate.test.js`: esbuild cannot
resolve `monaco-editor/esm/vs/editor/editor.api` (and related language
contributions) from the shared `node_modules` symlink. Pre-existing
environment/install issue; not a scoring defect.

## Frozen per-item v1 scores

Pinned inputs are the eight `scripts/scoring_regression.py` cases (question,
ideal, keywords, answer, engagement, difficulty). Observed results:

| id | final_score | guard_applied | nlp_score | kg_score |
| --- | --- | --- | --- | --- |
| excellent | 91.39 | null | 78.43 | 9.09 |
| paraphrase | 49.62 | null | 45.79 | 0.0 |
| partial | 56.1 | null | 45.18 | 9.09 |
| empty | 5.0 | empty | 0.0 | 0.0 |
| gibberish | 6.06 | repetition | 11.77 | 0.0 |
| excessive_repetition | 8.4 | repetition | 12.6 | 0.0 |
| keyword_stuffing | 10.0 | gibberish | 52.29 | 0.0 |
| off_topic | 12.5 | off_topic | 22.13 | 0.0 |

Replay: `python scripts/replay_scorer_v1_baseline.py`. Do not regenerate the
fixture to make a later run look like a pass.

## Historical human-baseline claims

`docs/human_baseline_report.md` was restored to the committed 230-line form
after pytest (`tests/test_change5_baseline.py` / `scripts/baseline_analysis.py`)
rewrote it to the n=30-only 68-line document. Restored MD5
`5421f9f0fd6efad395666c545e5cf76a`. This is a known suite side effect (see
`docs/review_guide.md`); the file is not part of this phase's intended diff.

The committed report contains the n=30 combined-xlsx section (Pearson r =
0.7392) and the appended n=50 validation study (Pearson r = 0.730, band
agreement 56%, κ = 0.290, Poor-label system mean 46.0 vs human 10.9). Those
are historical report claims until reproduced with a new run ID.

Recomputing the n=50 figures needs `scripts/verify_baseline_v2.py` (untracked
on Tree 2) plus the Google Forms workbook
`data/interViv — Answer Rating (Responses).xlsx` (also untracked on Tree 2,
absent here). Those files were inspected and not copied, to avoid importing
Tree 2 WIP. `data/baseline_v2_system_scores.csv` is hashed as a committed eval
artifact but was not regenerated.

## Tag

Local annotated tag `baseline/unify-shell-6659fed` is intended for this exact
commit. A tag does not capture runtime caches or MiniLM weights.
