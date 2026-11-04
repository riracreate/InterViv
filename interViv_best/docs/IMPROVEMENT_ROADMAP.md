# InterViv improvement roadmap

Research and repository review: **2 November 2026**. This is a proposed product
and engineering sequence. Only the changes listed in
[the maintenance record](maintenance_2026-11-02.md) have been implemented.

## Product direction

Build a dependable practice loop: **choose a target → answer → understand one
specific weakness → practise it → demonstrate improvement on a new question**.
The existing application already has practice modes, target profiles, reports,
review scheduling, and progress storage. Connect those pieces before expanding
the feature list.

The initial audience hypothesis is students and junior software candidates,
based on the current question packs and company-role flows. Validate this with
five observed sessions: can a learner choose useful practice, interpret the
feedback, and decide what to do next without explanation? This is proposed
research, not a completed user study.

AI mock interviews alone are unlikely to distinguish the product. Interviewing.io
offers AI coding/system-design practice alongside human interviews; Aced
(formerly Exponent) offers peer and AI practice. Those are feature observations
from their own sites, not independent evidence of effectiveness.
[Interviewing.io](https://interviewing.io/), [Aced practice](https://www.aced.io/practice).

Our differentiation hypothesis is **affordable, reliable practice with feedback
that shows its evidence and progress measured on fresh questions**. Offline
questions and low-bandwidth text practice can support this. Demand and willingness
to pay remain untested.

## What to build next

| Order | Work | User benefit | Completion evidence | Relative effort |
|---|---|---|---|---|
| 1 | Finish release verification | A fresh installation behaves like this working machine | Supported frontend toolchain; successful Linux, PostgreSQL, container and browser checks; one canonical GitHub branch | Small–medium |
| 2 | Calibrate feedback with human ratings | Feedback earns trust | Fresh independently rated answers; agreement/error by topic; disagreement examples reviewed | Medium plus reviewer time |
| 3 | Make one next action obvious | Learners know what to practise today | Five observed users complete practice, read feedback and start the recommended follow-up | Medium |
| 4 | Connect reviews to transfer practice | Improvement lasts beyond one memorized answer | Delayed, unassisted answers on unseen equivalent questions improve in a pilot | Medium |
| 5 | Verify coding and speech as complete flows | Optional tools work predictably | Executor success, timeout, unavailable-runtime and recovery checks; editable transcript before scoring | Medium |
| 6 | Prepare a small hosted pilot | Accounts and results remain dependable | PostgreSQL/Redis exercised, backup restored, account recovery and data controls tested | Medium |

Effort is relative, not a delivery estimate. Finish each acceptance check before
expanding that part of the product.

## 1. Finish release verification

The local launcher now preserves progress, authentication attempts are limited,
resume extraction failures are explicit, and the navigation panel works with
the keyboard. Tests pass locally. The remaining release work is concrete:

- Upgrade Vite from the installed 5.4.21 to a supported release and verify editor
  workers, tests, and build. The dependency-install request was declined during
  this session, so manifests and installed packages were not upgraded. Vite's
  current policy lists 7.3 among supported lines; 5.x is outside support.
  [Vite release policy](https://vite.dev/releases).
- Run the added GitHub workflow on a reconciled branch. It covers backend,
  frontend, PostgreSQL write behavior, and container readiness. It has not run
  remotely yet. Keep local research responses and backup credentials private.
- Validate dependencies from a clean Linux environment. The new Python version
  constraints capture this machine; they are not a verified cross-platform lock.
  Keep trained artifact metadata tied to the environment that produced it;
  scikit-learn does not support arbitrary version changes when loading saved
  models. [Model persistence guidance](https://scikit-learn.org/stable/model_persistence.html).
- Add a small browser flow to CI: create an account, practise, submit, open the
  report, reload, and verify saved progress. Include keyboard navigation and one
  narrow viewport. The current smoke script proves the API flow and restart
  persistence; browser interaction was checked manually this session.
- Measure first-page loading separately from the coding editor. The editor and
  language worker chunks are large; load heavy tools only when needed. First
  measure actual route loading before splitting bundles merely to remove warnings.

## 2. Make feedback defensible

The new classifier evaluation keeps normalized question groups separate between
training and validation. Grouped splits prevent answers to the same question
from crossing those boundaries. Semantically equivalent paraphrases may still
cross groups; review duplicates before treating this as a final benchmark.
[scikit-learn grouped validation](https://scikit-learn.org/stable/modules/cross_validation.html).

The run used 891 labeled answers and 245 question groups. Training contained
723 answers/196 groups; validation contained 168 answers/49 groups, with zero
normalized-question overlap. Validation accuracy was **92.86%** and macro F1
was **0.928**. These measure agreement with existing dataset labels, not human
agreement, score calibration, employability, or learning benefit. Production
model files were not replaced. See [the run record](../research/grouped_evaluation.json).

Use the existing [annotation protocol](baseline_v2_protocol.md) and
[held-out gates](track2_heldout_protocol.md) as the starting point. The latter's
fresh independent ratings remain outstanding; the old response workbook is
not a substitute. Keep `LENGTH_RATIO_MULTIPLIER_ENABLED` off until the stated
gates pass. Never synthesize human ratings to finish the study.

For each feedback item, show the rubric concept, the learner's supporting text,
what is missing, and one actionable revision. Show “not assessed” when the
question, transcript, or reference cannot support a judgment. Include short
correct answers, verbosity without substance, misconceptions, paraphrases, and
off-topic answers in the reviewed set. Separate factual content quality from
delivery coaching; optional camera activity should not become a competence score.

Record question/rubric/model versions with results. Report human disagreement
alongside model disagreement, with per-topic errors and uncertainty intervals.
Change a scoring rule only on development data, then evaluate on fresh data.

## 3. Simplify the daily experience

Proposed primary navigation: **Home, Practice, Progress**. Put Resume, Jobs,
Resources and specialist tools in a secondary area while retaining their routes.
Test the grouping with users before implementing a broad redesign.

Home should answer three questions: What is my target? What should I practise
next? What changed since last time? Use one primary action, a short explanation
of why that exercise was chosen, and an honest estimate of session length.
Keep target profile coverage and the amount of evidence visible; a readiness
number should not imply a hiring probability.

After a session, foreground one strength, one weakness, and one follow-up action.
Keep the detailed rubric available. Examples: “Explain the join condition in
one sentence,” or “Solve a new problem using the same data structure.” Track
whether the learner takes the follow-up, not just whether a report was opened.

## 4. Turn practice into learning

Research supports retrieval practice and distributing practice over time across
many learning settings. This motivates connecting the existing review scheduler
to active recall and fresh questions; it does not establish that InterViv
improves interview or hiring outcomes.
[Dunlosky et al., 2013](https://acs.ist.psu.edu/ist521/dunloskyRMNW13.pdf).

Offer a retry after feedback, then a delayed review on a different question
testing the same concept. A 1/3/7-day schedule is an experiment to evaluate,
not a universal research-prescribed interval. Preserve the difference between
assisted attempts and unassisted checks. Avoid raising mastery solely because
someone copied the explanation or repeated an identical answer.

Run a small opt-in pilot with an initial unseen assessment, several practice
sessions, and a delayed unseen assessment. Compare equivalent difficulty and
topic coverage. Examine who drops out and why; completion and return rates
alone cannot establish learning.

## 5. Complete optional flows

Coding already has an isolated local execution design and an availability
endpoint. Exercise the real service next: each supported language, correct and
incorrect solutions, timeout, runtime missing, service down, draft restoration,
and duplicate submission. The executor was not started or validated in this
maintenance session.

Update 2026-11-03: the overhaul replaced "no host execution" with one explicit
exception. `scripts/run_local.py --trusted-local-execution` runs Python coding
and NumPy ML Primitives in local worker processes so the demo works without
Docker. The backend honours it only in development on a loopback bind host.
It is a trusted local runner for your own code, not a sandbox, and it is never
a silent fallback: without the flag, missing Piston still means "execution
unavailable". Shared or hosted deployments must keep using the isolated
executor. Limits and evidence: `coding_execution_security.md` (trusted local
runner section).

For speech, let the learner review and edit the transcript before grading.
Test noisy audio, interrupted recording, permission refusal, and text fallback.
Move long transcription jobs to a queue only when measurements show the current
request path is inadequate. Keep live question generation and job fetching
explicitly enabled, with timeouts and visible fallback/source status.

## 6. Pilot operations and success measures

Retain React, FastAPI, and the existing SQL persistence layer. Use SQLite for
local work and PostgreSQL for the shared pilot. Configure Redis for counters
shared across workers. Exercise the deployed reverse proxy so client-based
limits distinguish users without trusting arbitrary forwarded headers.

Before inviting external users, complete account recovery, email verification,
data export/deletion, private storage handling, and a tested backup restore.
Measure failed requests, submission retries, request latency, and external
provider cost without logging passwords, tokens, resumes, or answer text by
default. Auth hardening in this session adds bounded attempts and PBKDF2-SHA256
at 600,000 iterations with legacy verification; this is one part of release
hardening, not a complete security certification.
[OWASP password storage guidance](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html).

| Measure | Why it matters | How to assess |
|---|---|---|
| First-session completion | Whether onboarding works | Target selection → submitted session, with drop-off reasons |
| Feedback usefulness | Whether explanations produce action | Observed understanding, corrections, and follow-up completion |
| Delayed unseen performance | Whether learning transfers | Equivalent new questions, unassisted, with independent ratings |
| Scoring reliability | Whether feedback is calibrated | Agreement, absolute error, and disagreement examples by topic |
| Persistence and recovery | Whether results can be trusted | Restart, interrupted submission, duplicate request, backup restore |
| Speed and cost | Whether the experience is sustainable | p50/p95 latency, slow-path failures, cost per completed session |

Set numerical pilot targets before collecting results and revise the product
based on the evidence. Defer new agents, more dashboards, broad model retraining,
and additional practice modes until the core loop is reliable and useful.
