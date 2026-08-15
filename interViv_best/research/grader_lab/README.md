# interViv grader lab

`research/grader_lab` is an evaluation-only comparison harness for diagnostic short-answer grading, follow-up evidence resolution, and feedback auditability. It imports the current scorer through its existing interface and does not change production application logic.

## Included comparisons

- Content-token lexical similarity.
- Pinned `sentence-transformers/all-MiniLM-L6-v2` semantic similarity with an inspectable negation/antonym contradiction heuristic.
- The current interViv scorer/guard pipeline through a research adapter.
- A structured LLM rubric judge registration that is explicitly `deferred` and has no client or network path.

The non-executable placeholder configuration is in [`structured_judge_config.example.json`](./structured_judge_config.example.json). It hard-disables execution and allows zero calls until cost, latency, provider, model, privacy, and API policy are explicitly scoped.

The current pipeline's local embedding component is enabled by default in lab runs, matching the production default. Pass `--disable-interviv-semantic` only for an explicit fallback experiment. Both semantic paths use local checkpoints; the harness sets offline mode and never downloads a model.

## Data

All examples use [`schema.json`](./schema.json) and the runtime validator in `schema.py`.

- SciEntsBank and BEETLE: normalized official 5-way `Core` test partitions. See [`DATASET_LICENSES.md`](./DATASET_LICENSES.md) and the data attribution notice.
- Internal perturbations: synthetic off-topic, vague, keyword-stuffed, contradictory, partial, clean-control, and follow-up/resolution cases.
- RiceChem: optional. Its absent file produces `pending_access`, not a failure.

To reproduce normalization from the organizer's extracted `semeval-5way.zip`:

```bash
python -m research.grader_lab.import_semeval /path/to/extracted/semeval-5way
```

## Run

From `interViv_best` with the project environment active:

```bash
python -m research.grader_lab.run
python -m research.grader_lab.ablation
python -m research.grader_lab.contradiction_analysis --baseline semantic_nli_relevance
python -m pytest research/grader_lab/tests -q
```

Outputs are written to `research/grader_lab/results/`. Every CSV row repeats the complete manifest fields, and the Markdown report contains the same git commit, dataset versions, and baseline model/checkpoint versions. The report explicitly separates benchmark-validated metrics, synthetic pilot metrics, deferred baselines, and pending-access datasets.

`resolved_evidence_rate` is computed only for internal follow-up records. All such output rows are stamped `pilot_synthetic=true`; the SemEval and future RiceChem rows must never be presented as validation of follow-up resolution.

## Metric semantics

- Grading accuracy and macro-F1 use the five SemEval labels.
- Off-topic false-positive rate is the rate of explicit off-topic flags among gold on-topic answers.
- Off-topic detection rate is explicit off-topic recall over gold irrelevant/non-domain answers; it is separate from false-positive rate.
- Contradiction detection rate is recall over gold contradictory answers.
- Unsupported-feedback rate divides unsupported feedback claims by emitted feedback claims and is `N/A` when no feedback exists. The two claim counts are reported separately.
- Evidence-citation completeness counts statements with a valid explicit `rubric.*` or `concept.*` ID.
- Resolved-evidence rate is exact trigger-gap resolution judgment accuracy on the internal follow-up pilot.

Citation completeness is a structural auditability measure, not proof that a statement is correct. The claims ledger preserves that distinction.

`SEMANTIC_RUNTIME_DIAGNOSIS.md` records why the historical interViv comparison used lexical fallback. The baseline-agnostic contradiction analyzer operates only on gold contradictions missed by its configured target. Automatic taxonomy labels are exploratory; unresolved cases remain `OTHER` with `review_required=true`.

`ablation.py` is research-only. It compares the full pipeline with the production lexical fallback, removal of individual final aggregation terms, and removal of the hard guard cap/flag. The term-removal variants renormalize remaining base weights but retain correlated upstream features, so the report labels that limitation explicitly.
