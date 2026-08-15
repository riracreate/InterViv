# Experiment freeze: CINS 2026 manuscript candidate

Frozen on 2026-08-15 for manuscript drafting. Do not replace a result or quote a number without generating a new manifest-stamped run and updating this file.

## Scope and status

- Production application logic: unchanged.
- Primary comparison run: `grader-lab-20260815T160016Z`.
- Research-only ablation run: `grader-lab-20260815T161227Z`.
- Contradiction miss analysis: `grader-lab-20260815T161440Z`.
- Repository commit recorded by all runs: `8758ecfed5171176add2d1905173aeac58ee914a`.
- Worktree at execution: `dirty=true` because the research module is not committed.
- Structured LLM rubric judge: `deferred_zero_api_calls`; the comparison remains incomplete.
- RiceChem: `pending_access`; absent and not analyzed.
- Follow-up resolution: internal synthetic pilot only (`pilot_synthetic=true`).

## Semantic execution gate

The primary run and ablation both recorded 7,110 applicable interViv predictions, 7,110 semantic function calls, and zero semantic fallbacks. The contradiction analysis recomputed 894 additional interViv predictions with 894 semantic calls and zero fallbacks. These counters establish research-runtime execution, not deployed-service behavior.

## Frozen artifacts

| Artifact | SHA-256 |
| --- | --- |
| `results/grader_lab_results.csv` | `cb3c931508d80d08245004c70e199f09312e31d716b96000f9f481a9e6b28a35` |
| `results/grader_lab_report.md` | `32cb12974461392dd4a0aad34ae8a7ff86842956201a5a69a28b2e9c9c13683c` |
| `results/interviv_ablation_results.csv` | `229bdb858ab793094191a87f255c70cd305963fcf483c3bbec6d7c4115e7d2f3` |
| `results/interviv_ablation_report.md` | `2715f4d53a27a285715c63422e16d741afc5045e8b8d49ac17db3515a669e202` |
| `results/contradiction_error_analysis.csv` | `5430d532baa8c7bc5c6b9895af69f118294ce9836f584b2636497f8384eea53b` |
| `results/contradiction_error_analysis.md` | `9a8615be8f9e59a4c6008727d121e13b90f0916a2be09b8058b9631a1c14d35a` |
| `data/internal_perturbations.jsonl` | `6a28c698b5e1d413c3be1074e4ee3b39eca7f6fafd938d758475e75d4e52eaed` |

## Model and dataset identity

- Embedding model: `sentence-transformers/all-MiniLM-L6-v2`, revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`.
- Classifier: `LogisticRegression` version `1.1.0`, artifact SHA-256 `2897c8cc6283cbdb4815a78182188ea60c17b39876feefa2d67919f065f16dd7`.
- SciEntsBank and BEETLE: SemEval-2013 Task 7 five-way Core test partition at organizer revision `5157c69f914e8c581045c03e98f96398d40a91b8`.
- SciEntsBank normalized examples: 5,835; SHA-256 `5458a915f162bd52c6402ad1538d96691bc9161ca4c51e5f2c400bd6ffe554c2`.
- BEETLE normalized examples: 1,258; SHA-256 `4ae5156dbbcb9a9afe25d050cc5ab37c341461bc342739c4de1bac4bddd831d9`.
- Internal perturbation examples: 17; version `grader-lab-perturbations-v1`.

## Manuscript interpretation lock

The frozen evidence does **not** support claims that interViv outperforms the semantic baseline, detects contradictions, detects off-topic answers more reliably overall than lexical scoring, or improves learner readiness. Evidence-citation completeness is a structural traceability measure only. The structured-judge comparison is deferred, and the synthetic follow-up pilot is not benchmark validation.
