# Phase 1A — reviewed-bundle infrastructure

Branch `phase1a/reviewed-bundles`, worktree `.worktrees/cursor-ai-design-phase1a`,
based on Phase 0 tip `0c259c1614b115076b46aceb83cc908b31fc89d6`.

Scope: storage, canonical content, import, review tooling, inventory, selector
contract, and evaluation separation. **Not** in scope and not done: rubric v2 /
concept evaluator (Phase 1B), production activation of reviewed-only
selection, any scorer change, hint coach, Phase 2.

## Actual review status

**No bundle has been reviewed by a human.** Twelve pilot drafts exist
(`status = draft`, `source = imported_csv`). Every review record the code can
produce requires two distinct authenticated admin identities acting through
the routes; the tests create synthetic records only in disposable stores.
Nothing in this phase may be described as "reviewed content".

## Design

### Authority

| Where | What it owns |
| --- | --- |
| `data/question_bundles/<skill>/<bundle_id>.yaml` | Canonical **content + provenance** (question, reference, concepts, misconceptions, rubric descriptors, followups, calibration examples; `source`, `author`, `attribution`). Never review state — the validator rejects `status`/`reviewed`/`approved`/… keys. |
| DB tables | Materialised content per version **plus** review state: `status`, decisions, audit trail. |

Editing content means bumping `version` in the YAML. The store refuses the
same version number with a different hash, refuses identical content under a
new number, and refuses version gaps. Reviewed versions stay reviewed until
retired; a new version starts as `draft`.

### Content hash

`sha256` of the canonical JSON (`sort_keys`, compact separators) of
`CONTENT_FIELDS` in `modules/question_bundles.py`, after whitespace
normalisation of strings. `version`, `source`, `author`, `attribution` are not
hashed. Every review decision and audit row stores the hash it applied to.

### Tables (Alembic `20260913_0010`, revises `20260908_0009`)

| Table | Purpose | Constraints |
| --- | --- | --- |
| `question_bundles` | identity: `bundle_id` (PK), `category`, `skill`, `topic` | — |
| `question_bundle_versions` | immutable content: `id = "<bundle_id>@<version>"`, `version`, `difficulty`, `content_json`, `content_hash`, `source`, `attribution_json`, `author_id`, `status`, timestamps | `UNIQUE(bundle_id, version)`, `UNIQUE(bundle_id, content_hash)`, `CHECK version >= 1`, `CHECK status IN (draft, in_review, reviewed, rejected, retired)` |
| `bundle_review_decisions` | one human decision bound to `(bundle_id, version, content_hash)`: `reviewer_id`, `decision`, `checklist_json`, `reasons`, `calibration_json` | `UNIQUE(version_id, reviewer_id)`, `CHECK decision IN (approve, reject, adjudicate_approve, adjudicate_reject)` |
| `bundle_status_audit` | append-only `from_status → to_status`, `actor_id`, `reason`, `content_hash` | — |

Additive only. Existing tables, rounds, reports, and the scorer are untouched.

**Rollback:** `alembic downgrade 20260908_0009` drops the four tables. Content
is recoverable from YAML; review decisions and audit rows are human evidence
and are **not** recoverable — export them first if a database holds real
reviews. No pre-existing row changes in either direction. Verified on a
disposable SQLite file: upgrade → import → re-import (12 unchanged) → downgrade
(tables gone, `alembic_version` back to `20260908_0009`).

### Store (`modules/bundle_store.py`)

Memory backend when `DATABASE_URL` is absent, SQLAlchemy otherwise; identical
document shapes so every rule is written once. There is **no update path for
content**; `status` is the only mutable column and `_transition` is its only
writer, always appending an audit row.

Rules enforced (and tested):

- import idempotent: same version + hash → `unchanged`; same version, other
  hash → `conflict` naming both hashes and the next version number; identical
  content re-numbered → `conflict`; version gap → `conflict`; changed
  category/skill/topic on an existing `bundle_id` → `conflict`
- decisions only while `in_review`; approve/reject on `draft`, `reviewed`,
  `rejected`, `retired` → `conflict`
- `content_hash` in the decision must equal the stored hash → else stale →
  `conflict`
- reviewer ≠ author → else `forbidden`; one decision per reviewer per version
- evidence: all seven checklist keys explicit booleans; approval cannot carry a
  failing item; `reasons` ≥ 20 chars and not a placeholder (`lgtm`, `ok`,
  `TODO`, …); `calibration.difficulty` (blind rating) required
- approval requires non-empty `required_concepts` (a bundle with none cannot be
  assessed)
- two distinct approvals, no reject → `reviewed`; two rejects → `rejected`;
  one of each → stays `in_review`, `needs_adjudication = true`; a third
  identity (not author, not either reviewer) records `adjudicate_approve` /
  `adjudicate_reject`
- `retire` only from `reviewed`, with a substantive reason

### Admin routes (`backend/routes/admin.py`)

Mounted only when `ENABLE_ADMIN_ENDPOINTS=true` (existing gate). Each route
additionally calls `require_admin`: a valid bearer token (401 otherwise) whose
user email is in `ADMIN_USER_EMAILS` (403 otherwise; empty list = nobody).
Reviewer identity is the token's user id; a `reviewer_id` in the body is
ignored.

| Route | Purpose |
| --- | --- |
| `GET /admin/bundles?skill=` | bundles with version summaries (no content) |
| `GET /admin/bundles/inventory` | reviewed counts skill → topic → difficulty; unreviewed (draft + in_review) separately; status totals; `reviewed_only_enforced` |
| `GET /admin/bundles/{id}/versions/{v}` | reviewer view: full content **minus author labels** (`difficulty`, `calibration_examples[*].author_level`) plus decisions, audit, `needs_adjudication` |
| `POST …/submit` | draft → in_review |
| `POST …/decisions` | `{content_hash, decision, checklist, reasons, calibration}` |
| `POST …/retire` | reviewed → retired with reason |

Store error codes map to 422 invalid / 409 conflict / 404 not found / 403
forbidden. No frontend page was added (backend + CLI prioritised).

### Selector (`modules/bundle_selector.py`) and flag

`select_reviewed_question(skill, difficulty, asked, topic)` returns the
candidate payload of the first eligible latest-`reviewed` version not already
asked, or raises `ReviewedInventoryUnavailable`. Draft, in_review, rejected and
retired versions are never eligible. The payload
(`modules.question_bundles.candidate_payload`) contains identity + question
only — no reference answer, keywords, concepts, misconceptions, descriptors, or
calibration material.

`REVIEWED_BUNDLES_ONLY` (default `false`) is read into `Settings` and reported
by the inventory endpoint. **It is not wired into `_get_next_question`.**
Reason found during this phase: the technical round contract stores the full
question payload (including `ideal_answer`) in `question_context`, and
`sanitize_round_for_client` passes `technical_short_answer` context through
unchanged, so a reviewed bundle routed through today's path would put the
reference answer in the candidate response. Activation needs the round to
store a bundle reference (`bundle_id`, `version`, `content_hash`) and resolve
the reference server-side at scoring time, plus an allowlist in the serializer.
That is Phase 1B/2 work and is listed under blockers below.

### Evaluation separation (`modules/evaluation_overlap.py`)

Known evaluation items on this branch: `data/baseline_v2_key.csv` (100 items;
`row_id`), with `data/baseline_v2_system_scores.csv` marking the 50 that were in
the form study, and `data/human_baseline_real_combined.xlsx` (30 items).
Matching uses the established rule — exact text after whitespace
normalisation (`scripts/score_baseline_v2.py`, `docs/baseline_v2_protocol.md`)
— plus casefolding. Exact matches are **rejected** by the importer; token-set
Jaccard ≥ 0.6 flags a paraphrase, which is imported but recorded in
`attribution_json.evaluation_overlap` and printed for the reviewer. Two
candidate pilot questions were dropped because they were flagged (context
managers ↔ key rows 37/57; MRO ↔ rows 1/78).

## Import workflow

```
.venv/bin/python scripts/import_question_bundles.py --check      # validate + overlap only
.venv/bin/python scripts/import_question_bundles.py              # memory store (DATABASE_URL unset)
DATABASE_URL=sqlite:////tmp/x.db .venv/bin/alembic upgrade head
DATABASE_URL=sqlite:////tmp/x.db INTERVIV_USE_MEMORY_DB=false \
  .venv/bin/python scripts/import_question_bundles.py --actor <who-ran-it>
```

Exit 1 on any invalid file, conflict, or exact evaluation overlap. `--actor` is
the audit identity of the person running the import, not the content author
(`author` in the YAML).

## Review workflow (for the humans who have not yet done it)

1. Author (or importer) bumps/creates a YAML version, runs the importer.
2. An admin `POST …/submit` moves the draft to `in_review`.
3. Reviewer A opens `GET …/versions/{v}` (blind view), rates difficulty and any
   calibration examples, fills the seven-item checklist, writes reasons, and
   `POST …/decisions` with the `content_hash` from the view.
4. Reviewer B (different account, not the author) does the same independently.
5. Two approvals → `reviewed`. Two rejects → `rejected`. Split → a third admin
   records `adjudicate_*` with reasons.
6. Any content fix → new YAML version → back to step 1. Reviewed versions are
   retired explicitly, with a reason.

Model output cannot be a reviewer: identities are signed-up user accounts on
the allowlist, and the workflow records the token's user id only.

## Pilot draft inventory

12 bundles, all `draft`, all `imported_csv`, author
`dataset:interview_dataset_v6.csv#curated_v3`, question and reference copied
verbatim (source line recorded in `attribution_json`). Concept lists,
misconceptions, descriptors and rubric fields are intentionally empty — they
were not in the source and authoring them is a new draft version, not part of
this import.

| Skill | easy | medium | hard |
| --- | --- | --- | --- |
| Python | lists vs tuples (L5); `is` vs `==` (L26) | generators (L14); shallow vs deep copy (L20) | GIL (L8); memory management (L11) |
| DBMS | ACID (L170); JOIN types (L179) | normalisation 1NF–3NF (L173); OLTP vs OLAP (L200) | isolation levels (L188); deadlocks (L197) |

None overlap exactly or by paraphrase with the evaluation items. None can be
approved as-is (empty `required_concepts`), which is the intended gate.

## Verification

`tests/test_phase1a_bundles.py` (memory and migrated-SQLite parametrisation
where storage matters): hash stability, canonical-YAML validation, import
idempotency and every conflict, reviewed-version immutability with edits
becoming new drafts, DB unique constraints, migration downgrade scope, review
evidence rejection (author, stale hash, incomplete checklist, failing checklist
on approve, placeholder reasons, missing calibration, premature adjudication,
duplicate reviewer), approval-needs-concepts, two-approval transition + audit +
retire, split → adjudication, evaluation overlap exact-reject / paraphrase-flag
through the importer, repo pilot imports as 12 drafts with no overlap,
inventory counts, selector rejecting draft/asked/retired, candidate payload
excluding reference material, admin 401/403/404/409/422 and full route flow,
admin router absent by default.

`tests/test_phaseX_persistence.py` was updated only because its head assertion
named the previous head and its downgrade used `parent_revision("head")`
against the helper's own convention; it now names `20260908_0009`.

Phase-boundary results are in `docs/implementation/ai-design-status.md`.

## Blockers before Phase 1B and before activation

- **Human review has not happened.** Two subject-knowledge reviewers with
  accounts on `ADMIN_USER_EMAILS` are needed; nothing here substitutes.
- Pilot drafts need `required_concepts` (and ideally misconceptions /
  descriptors) authored as version 2 before any approval is possible.
- Round contract: store `bundle_id/version/content_hash` on the round, resolve
  the reference server-side, allowlist technical `question_context` in the
  serializer. Until then `REVIEWED_BUNDLES_ONLY` must stay off.
- Concept evaluator / rubric v2 (Phase 1B) is separate and unstarted.
- The n=50 form workbook, `scripts/verify_baseline_v2.py`, `README_BASELINE.md`,
  `tests/test_baseline_v2_figures.py` exist only as Tree 2 untracked files;
  they were inspected read-only and not imported. `~/Downloads/BuildForm.gs`
  (expected by `scripts/score_baseline_v2.py`) is absent.
