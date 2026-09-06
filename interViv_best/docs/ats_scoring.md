# ATS scoring (Ticket C)

Deterministic resume ↔ role/JD checker. No LLM judge.

## Formula

```
ATS = 0.25*ParseHealth
    + 0.20*SectionComplete
    + 0.40*KeywordCoverage
    + 0.15*ContentHeuristics
```

Each component is returned separately (0–100) so the UI can explain the total.

| Component | Weight | What it measures (given current parser) |
|-----------|--------|-----------------------------------------|
| ParseHealth | 0.25 | Starts at 100. Subtract for extract failure / garbage text. **Does not** detect multi-column or layout tables — when text extracts successfully we keep 100 and emit flag `extract_layout_unchecked`. |
| SectionComplete | 0.20 | Header heuristics for contact / experience / education / skills in extracted text (regex on section titles + email). Unusual header order −10. |
| KeywordCoverage | 0.40 | \|resume ∩ must_have\| / \|must_have\| after synonym expansion via `TECH_SKILLS` + role short-code aliases (OS→Operating Systems, CN→Computer Networks, HR→HR/Professional Judgment). JD path intersects JD text with the same lexicon — no LLM extract. |
| ContentHeuristics | 0.15 | Among experience-section bullets: fraction starting with a strong action verb + fraction containing a digit/metric (equal blend). |

## Persistence

`ats_runs` stores component scores, flags, present/missing skills, `resume_id` (candidate_id), optional `role_id`, `jd_hash` (not raw JD).

## Limitations we refuse to paper over

- No multi-column / table / image-only layout classifier in `resume_parser.py`.
- No rewriting resume text or LLM “phrasing tips”.
- Role must-have skills come from curated Phase 2 company-role profiles (or lexicon intersection for pasted JD), not scraped live JDs.
