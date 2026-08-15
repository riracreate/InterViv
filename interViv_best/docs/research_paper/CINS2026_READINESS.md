# CINS 2026 submission readiness

Status checked: 2026-08-15.

## Decision

**Do not present the anonymous manuscript candidate as a complete or currently submittable CINS 2026 comparison.**

The official CINS 2026 homepage currently lists **15 July 2026** as the submission deadline and **31 August 2026** as the acceptance-notification date. The supplied planning note reverses those roles. Unless the chairs have granted an extension or invited a late submission, the regular deadline has passed. Source: [CINS 2026 official homepage](https://cins2026.com/).

The supplied anonymous, maximum-six-page constraint was followed. The rendered candidate is three A4 pages. The public homepage view did not provide enough retrievable detail to independently verify the requested anonymous/page-limit formatting, so the actual author kit must still be checked before any venue upload.

## Evidence readiness

- Primary benchmark, research-only ablation, and contradiction-error runs are frozen with complete manifests.
- The corrected pipeline made 7,110/7,110 applicable semantic calls with zero fallback in both the primary comparison and ablation.
- Results do not support broad claims of diagnostic superiority, reliable off-topic detection overall, contradiction detection, or improved learner readiness.
- Evidence-citation completeness supports structural traceability only; citation correctness needs human adjudication.
- Follow-up resolution remains `synthetic_only` on four constructed cases.
- The structured LLM rubric judge is `deferred_zero_api_calls`; the comparison is explicitly incomplete.
- RiceChem remains `pending_access`.

## Artifact QA

- Anonymous DOCX metadata scrub: passed.
- Visible identifier and package-string scan: passed.
- Final render: three A4 pages, reviewed page by page; no clipping, overlap, or broken tables observed.
- Final PDF: no custom metadata, JavaScript, forms, encryption, or PDF structural suspects reported.
- Manuscript artifact hashes and experiment run IDs are recorded in `interViv_cins2026_manifest.json`.

## Gates before a real submission

1. Confirm an authorized late-submission route or choose another open venue.
2. Obtain and apply the actual venue author template and current anonymity rules.
3. Implement the structured LLM judge only after provider, privacy, cost, latency, and API policy are approved; rerun and freeze a new comparison.
4. Human-adjudicate contradiction misses and evidence-citation correctness.
5. Calibrate only on development data and preserve untouched benchmark test partitions.
6. Keep learner-readiness claims out until a consented, blinded longitudinal study exists.
