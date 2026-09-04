# Phase 2 SQL Difficulty Rubric and Classification Record

Target distribution: **10 easy / 12 medium / 8 hard** (30 problems, 90 cases).

## Rubric

**Easy:**

- Basic filtering, projection, or one straightforward aggregation.
- Little or no multi-stage reasoning.

**Medium:**

- Multiple logical steps.
- CTEs, window ranking, conditional aggregation, or pivot-style output.
- Moderate edge-case handling.

**Hard:**

- Several interacting transformations.
- Nested/multiple windows or complex temporal/cohort logic.
- Multiple subtle edge cases where plausible solutions fail.

## Classification decisions for `sql_prob_026` and `sql_prob_030`

Both problems were reclassified from hard to medium during the repair cycle.
Each is evaluated below against the rubric above on its own merits; neither
label was changed solely to satisfy counts.

### `sql_prob_026` — Top Two Salary Ranks per Department → **medium** (retain)

- Reference solution: a single CTE with one `DENSE_RANK()` window partitioned
  by department, then a `rank <= 2` filter. One ranking step plus one filter step.
- The prompt explicitly names `DENSE_RANK()`, so the technique is given, not
  discovered. The remaining work is partitioning, tie inclusion, and the
  four-key `ORDER BY`.
- Hidden cases exercise genuine edge handling (ties for second rank,
  single-employee departments), which lifts it above easy, but there are no
  interacting transformations, nested windows, or temporal logic.
- Verdict: satisfies Medium (multiple logical steps + window ranking +
  moderate edge cases). Does not satisfy Hard. Retained as medium.

### `sql_prob_030` — Quarterly Category Sales Pivot → **medium** (retain)

- Reference solution: `GROUP BY category` with four `SUM(CASE WHEN ...)` pivot
  expressions plus `SUM`/`ROUND` totals. No window function, no CTE, no
  recursion, no temporal logic.
- Conditional aggregation with pivot-style output is listed verbatim under
  Medium. Hidden cases (missing quarters, decimals, revenue ties demanding the
  tie-break ordering) provide moderate edge-case handling above easy.
- Verdict: satisfies Medium. Does not satisfy Hard. Retained as medium.

## Current distribution (enforced by `test_sql_bank_size_and_case_distribution`)

- Easy (10): `sql_prob_001`–`sql_prob_010`.
- Medium (12): `sql_prob_011`–`sql_prob_020`, `sql_prob_026`, `sql_prob_030`.
- Hard (8): `sql_prob_021`–`sql_prob_025`, `sql_prob_027`, `sql_prob_028`,
  `sql_prob_029`.
