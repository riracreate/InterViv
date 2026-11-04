# Phase 1B pilot — human review checklist

All 12 Python/DBMS pilot bundles now have **v1** (CSV import, empty concepts) and **v2** (developer-authored concepts/rubrics). **Every version remains `draft`.** No reviews were fabricated.

## Reviewers required before any `reviewed` status

- Two distinct subject-knowledge reviewers whose emails are on `ADMIN_USER_EMAILS`
- Distinct from the content author (`phase1b-dev:concept-authorship` for v2; dataset attribution for v1)
- Admin routes only when `ENABLE_ADMIN_ENDPOINTS=true`

## Per-version checklist (must be explicit booleans)

| Key | What to verify |
| --- | --- |
| `question_clear` | Stem is unambiguous for the stated skill/topic |
| `reference_correct` | Reference answer is factually correct and sufficient |
| `required_concepts_right` | Required concept IDs/descriptors match what the question actually asks |
| `no_ambiguity` | No double-keyed reading that would make scoring unfair |
| `misconceptions_reasonable` | Listed misconceptions are real and patterns are not over-broad |
| `descriptors_observable` | Rubric descriptors can be observed in an answer without mind-reading |
| `calibration` | Blind difficulty rating recorded before seeing author labels |

Also required by the store: `reasons` ≥ 20 non-placeholder characters; `calibration.difficulty` present; non-empty `required_concepts` for approval (v2 satisfies; v1 cannot be approved as-is).

## Inventory to review first (v2 drafts)

| Bundle | Skill | Difficulty | Topic |
| --- | --- | --- | --- |
| `python.is-vs-equals` | Python | easy | Identity and equality |
| `python.lists-vs-tuples` | Python | easy | Core data structures |
| `python.generators` | Python | medium | Iteration and generators |
| `python.shallow-vs-deep-copy` | Python | medium | Object copying |
| `python.gil` | Python | hard | Concurrency and the GIL |
| `python.memory-management` | Python | hard | Memory management |
| `dbms.acid-properties` | DBMS | easy | Transactions |
| `dbms.join-types` | DBMS | easy | SQL joins |
| `dbms.normalisation-1nf-3nf` | DBMS | medium | Normalisation |
| `dbms.oltp-vs-olap` | DBMS | medium | Workload types |
| `dbms.deadlocks` | DBMS | hard | Concurrency control |
| `dbms.isolation-levels` | DBMS | hard | Transactions |

## Provenance note

v2 concept/rubric/calibration text is **developer-authored for offline development**. It is not human ground truth and must not be misattributed to the CSV author or to reviewers.
