# interViv — ICONAT 2026 Research and Writing Pack

Prepared: 3 July 2026
Target track: **Machine Learning, Cloud and Data Analytics**
Purpose: structured source material for a conference paper; this is **not** the full paper.

## 0. Submission alert and evidence boundary

The project brief states a submission deadline of **10 July 2026**, but the [official ICONAT 2026 Important Dates page](https://iconat.org/important-dates/) currently lists **20 June 2026** as the last date to submit a paper and contains inconsistent acceptance/camera-ready dates. Verify the live CMT portal or contact the organizers immediately. Do not plan solely around 10 July.

The [official call for papers](https://iconat.org/call-for-papers/) includes the selected **Machine Learning, Cloud and Data Analytics** track. The [submission guidelines](https://iconat.org/submission-guidelines/) specify an IEEE two-column, 10-point PDF, 6–8 pages including figures, tables, and references; single-blind review; CMT submission; and PDF eXpress checking after acceptance. A separate author-information page says six pages for the final paper, so the safest working target is **six pages including references**, pending organizer confirmation.

Evidence rules for this paper:

- Treat the 891-row classifier results as **classifier-only validation**, not whole-platform accuracy.
- Treat the 30-answer/three-rater set as a **small preliminary human baseline**, not proof of educational effectiveness.
- Treat the 200-row persona dataset as **simulation-based stress testing**, not a human-participant study.
- Describe interViv as a formative **interview-readiness** system, not a hiring predictor, credential, or replacement for human interviewers.
- Any proposed learning-effect or usability claim below is marked **Needs empirical support.**

## 1. Extracted project specification

### Project identity and summary

**Project name:** interViv — Interview Readiness Platform.

**Summary:** interViv is a full-stack, resume-aware platform for adaptive technical-interview practice. It uses a large language model only to generate structured questions and reference material; deterministic Python modules score answers, apply anti-gaming caps, update learner state, select weak concepts, calculate role gaps, generate roadmaps, and populate an explainable dashboard. The system supports typed, spoken, and optional camera-assisted interaction while preserving a strict boundary between generative content and assessment.

**Completion interpretation:** The repository does not support describing the core software as merely “60% complete.” The Phase 2 feature checklist is implemented and the current automated suite reports **116/116 passing tests**. Publication readiness is lower because production deployment, a real student pre/post study, accessibility/mobile visual QA, and final conference formatting remain unfinished. Avoid assigning a new percentage unless the authors define how it is calculated.

### Problem statement

Students preparing for technical placements need repeated opportunities to explain technical concepts aloud, receive specific feedback, and practice questions aligned with their skills and target roles. Human mock interviews can be useful but are difficult to schedule and scale, while static question banks provide limited adaptivity and often fail to reveal why an answer is weak. Generative systems increase question variety, but allowing an opaque language model to judge candidate quality introduces repeatability, auditability, calibration, and fairness concerns.

interViv addresses this problem by separating generation from evaluation. An LLM may create a schema-constrained question, ideal answer, keywords, and follow-ups, but all candidate scoring and learning decisions are produced by deterministic modules. A persistent learner model tracks skill scores, Elo ratings, attempts, concept demonstrations, and target-role gaps; this state drives question difficulty, weak-concept selection, feedback, and study roadmaps. Whether this design improves student readiness or confidence **Needs empirical support.**

### Research gaps

- Many AI interview tools combine prompt generation and answer judgment inside the same LLM, reducing reproducibility and making score explanations difficult to audit.
- Existing mock-interview work often emphasizes realism or conversational behavior but gives less attention to deterministic open-answer scoring and adversarial input handling.
- Static interview banks rarely combine resume-derived skills, target-company/role references, concept mastery, and per-skill adaptive difficulty in one traceable pipeline.
- Automated short-answer grading research is usually evaluated as an isolated scoring task rather than embedded in a deployed-style readiness workflow with feedback, dashboards, and next-question selection.
- Keyword-overlap systems can be gamed by repetition, parroting, filler, or keyword stuffing; guard behavior is rarely treated as a first-class validity requirement.
- Evidence on student learning, confidence, fairness, and usefulness for this specific system is not yet available. **Needs empirical support.**

### Objectives and contributions

- **We contribute:** a schema-constrained LLM question-generation layer that produces interview questions and reference metadata but is prohibited from scoring, judging, or making hiring decisions.
- **We contribute:** a deterministic, multi-signal open-answer scoring pipeline combining semantic/lexical evidence, a trained logistic-regression component, keyword and TF-IDF evidence, knowledge-graph coverage, entity recognition, and fixed feedback rules.
- **We contribute:** an anti-gaming gate with explicit score caps for empty, gibberish, repetitive, too-short, parroted, low-density, off-topic, and keyword-stuffed answers.
- **We contribute:** an interpretable adaptive learner state using per-skill Elo, skill graphs, concept mastery, role-gap analysis, and weak-concept targeting.
- **We contribute:** a production-oriented web architecture with authentication, PostgreSQL persistence, cache/rate-limit hooks, fallback question generation, dashboards, and reproducible automated tests.
- **We contribute:** preliminary validation artifacts: a balanced 891-row classifier dataset, a 30-answer three-rater human baseline, a 200-row simulated-persona stress test, and guard/regression tests. Any claim of improved readiness **Needs empirical support.**

### Target users and use cases

- Undergraduate and postgraduate students preparing for internships or campus placements.
- Early-career software candidates practicing verbal explanations of technical concepts.
- Candidates targeting a supported company/role reference profile.
- Learners seeking resume-aware topic selection and weak-skill identification.
- Instructors or project evaluators studying transparent automated feedback and learner analytics.
- Research use cases: deterministic short-answer assessment, adaptive sequencing, guard robustness, and human-system agreement.

### Completed modules

| Module | Implemented behavior | Evidence |
|---|---|---|
| Authentication and persistence | JWT signup/login/me; SQLAlchemy/Alembic PostgreSQL; in-memory fallback | `backend/auth`, `backend/db`, migration |
| Resume processing | PDF text/skill extraction and domain mapping | `modules/resume_parser.py`, resume route |
| Session orchestration | Multi-skill sessions, configurable rounds, per-skill rotation | session models/routes |
| Question generation | OpenAI/OpenRouter-compatible LLM path, strict JSON schema, retry, cache, rate limit, CSV/template fallback | `question_runtime.py`, `question_bank.py` |
| Deterministic scoring | NLP layers, logistic regression, semantic similarity, TF-IDF, keywords, KG and NER evidence | scoring pipeline and scorer modules |
| Answer guard | Empty/gibberish/repetition/short/parroting/filler/off-topic/stuffing rules and hard caps | `answer_guard.py` |
| Adaptive selection | Gap-first or weakest-skill selection, weakest-concept targeting, Elo difficulty | `adaptive_question_selector.py` |
| Learner analytics | Skill graph, concept mastery, confidence bands, role gap and readiness | graph/mastery/gap modules |
| Roadmap | Deterministic 7-, 14-, and 30-day practice plans | `roadmap_generator.py` |
| Feedback | Rule-based strengths, weakness, and next-step payload | `c4_feedback.py` |
| Speech | Browser speech path plus Faster-Whisper server transcription | interview UI and `/transcribe` |
| Optional engagement signal | On-device face-expression classification; camera can be skipped | `engagement.js`, interview UI |
| Dashboard | Score, Elo, radar, rubric layers, timeline, gaps, mastery, roadmap | React/TypeScript dashboard components |
| Deployment hardening | Docker, Compose, Render/Vercel config, Redis/Sentry hooks, warm-up/load-smoke script | deployment files and Task 8 docs |
| Verification | 116 passing automated tests on 3 July 2026 | `pytest tests/ -q` |

### Pending work and realistic effort

Effort estimates are person-days for a prepared developer/researcher and are not guarantees.

| Pending item | Implementation/research note | Estimate | Before a near-term submission? |
|---|---|---:|---|
| Confirm deadline and page rule | Check live CMT and obtain written organizer confirmation because public pages conflict | 0.25 day | Essential |
| Conference paper condensation | Convert the extended manuscript into a six-page IEEE conference narrative | 2–3 days | Essential |
| Production deployment | Supply Render/Vercel/PostgreSQL/Redis/Sentry credentials, migrate, smoke-test HTTPS URLs | 1–2 days | Optional for initial paper; useful for demo |
| Rapid student usability pilot | Consent, recruit, run one session, clean/export data, analyze | 3–5 days if ethics approval/department permission already exists | Exploratory only |
| Strong student study | Multi-session or controlled study with adequate power and independent raters | 4–8 weeks | Later publication |
| Question-bank review | Resolve audit warnings and expand 53 fallback items with expert review | 2–5 days for a modest expansion | Optional |
| Accessibility/mobile QA | Keyboard, screen-reader, contrast, responsive layout, browser matrix | 1–2 days | Recommended |
| Privacy documentation | Consent form, retention schedule, de-identification plan, camera/audio notice | 1 day | Essential if collecting participants |
| Reproducibility release | Environment lock, run instructions, anonymized artifacts, model/data cards | 1–2 days | Recommended |

### Technology stack

Versions below distinguish locked frontend versions, declared backend minimums, and model provenance.

| Layer | Technology/version |
|---|---|
| Frontend | React 18.3.1; React DOM 18.3.1; React Router 6.30.3; Vite 5.4.21; TypeScript 5.9.3; Tailwind CSS 3.4.x; Recharts 2.15.4; Motion 11.18.2; Lucide React; face-api.js 0.22.2 |
| Browser media | MediaRecorder/Web Speech capabilities; optional webcam; audio WebM/Opus |
| Backend | Python 3.12.4 in the current shell; FastAPI >=0.115; Uvicorn >=0.30; multipart uploads; HTTPX >=0.28 |
| ML/NLP | scikit-learn >=1.4 (model metadata records 1.8.0); LogisticRegression artifact v1.1.0; sentence-transformers >=2.2; PyTorch >=2.0; NumPy >=1.26; pandas >=2.0; joblib >=1.4; NetworkX >=3.0 |
| Scoring | TF-IDF/cosine, keyword and n-gram coverage, engineered quality features, classifier, KG, NER, guard caps, deterministic C4 feedback |
| LLM | Configurable OpenAI or OpenRouter question generation; documented production choice OpenRouter with `anthropic/claude-haiku-4.5`; CSV/template fallback |
| Speech-to-text | Faster-Whisper >=1.0, `tiny.en`, CPU int8; browser voice input where available |
| Data/persistence | PostgreSQL; SQLAlchemy >=2.0; Alembic >=1.13; psycopg >=3.2; in-memory fallback; PyMongo remains declared for compatibility |
| Auth/security | bcrypt >=4.1; PyJWT >=2.8; configurable CORS and JWT secret |
| Production | Docker/Compose; Render backend; Vercel frontend; Redis >=5 cache/rate limit; Sentry SDK >=2 |
| Formats | CSV, XLSX, YAML, JSON/model metadata, Joblib, PDF resumes, WebM audio |

### Data sources and sample sizes

| Artifact | Size | Purpose | Important limitation |
|---|---:|---|---|
| `interview_dataset_v6.csv` | 2,319 rows; 773 each Good/Average/Poor; 11 skill labels | Questions, reference answers, labeled answer examples, audit/evaluation | Mostly Medium difficulty (2,055 rows); mixed provenance |
| `ml_training_data.csv` | 891 rows; 297 per class; 11 skills | Logistic-regression training/validation | Balanced curated dataset; not live student traffic |
| `fallback_question_bank.csv` | 53 structured questions; 12 skill labels; 8 company labels | Live deterministic fallback | Small and has audit warnings for some role labels |
| `company_hiring_graphs.yaml` | 8 companies, 16 roles, 80 role-skill requirements | Curated target-role reference profiles | Not proprietary or exact hiring criteria |
| `human_baseline_real_combined.xlsx` | 30 answers, 3 human annotators | Preliminary system-human agreement | Small; some mismatched answer/question cases |
| `persona_validation_final.xlsx` | 200 rows, 4 simulated annotator personas | Controlled stress testing | LLM-persona simulation, not real human evidence |
| Model metadata | Held-out accuracy 0.9553; macro F1 0.9551; five-fold accuracy 0.9562 ± 0.0148 | Classifier validation | **Classifier only. Needs empirical support** before any whole-system claim |
| Human baseline report | mean Cohen’s κ 0.642; system–human Pearson r 0.7392, n=30 | Preliminary external agreement | Small sample. **Needs empirical support** through expansion |

### Privacy and ethical considerations

- Obtain informed consent before collecting resumes, answers, audio, camera-derived signals, surveys, or demographic data.
- Minimize collection: store extracted skill tags rather than complete resumes when possible; never include names, emails, tokens, or raw resumes in research exports.
- The server transcription route writes audio to a temporary file and deletes it in `finally`; document this behavior and define whether any upstream logs retain payload metadata.
- Face-expression inference runs in the browser, but derived engagement labels/confidence may be submitted. Treat those as sensitive behavioral data, keep camera use optional, and avoid interpreting expressions as emotion, honesty, competence, or employability.
- Do not use engagement, time, accent, fluency, or disability-correlated features to alter technical correctness scores without a separately validated fairness study.
- Use participant IDs, encrypted storage, least-privilege access, a retention/deletion schedule, and separate consent/contact records from response data.
- Obtain institutional ethics/IRB/IEC approval or a written exemption before human research when required. Do not backdate approval.
- State explicitly that company profiles are curated public-reference practice profiles, not exact recruiter criteria.
- Audit performance by subgroup only with consent and adequate sample sizes; avoid publishing identifiable small-cell demographics.
- Preserve the system boundary: LLM-generated content may contain errors, so question/reference quality requires review and fallback behavior.

## 2. ICONAT-tailored paper outline

### Recommended title

**interViv: A Guarded Adaptive Interview-Readiness Platform with LLM-Generated Questions and Deterministic Scoring**

Alternatives:

- **Separating Generation from Evaluation in an Adaptive Technical Interview Practice Platform**
- **Explainable Adaptive Interview Practice Using Constrained LLM Question Generation and Deterministic Learner Analytics**

### Abstract placeholder

Use the provisional 177-word abstract in Section 7 after replacing bracketed fields and selecting only results that fit the final study. IEEE recommends a self-contained single-paragraph abstract of no more than 250 words and 3–5 keywords; the ICONAT page limit makes 150–190 words preferable.

### Keywords

Adaptive learning; automated short-answer grading; interview readiness; large language models; learning analytics.

### Recommended six-page budget

| Content | Approximate pages |
|---|---:|
| Title, abstract, introduction | 0.75 |
| Related work | 0.65 |
| System and methodology | 1.75 |
| Evaluation setup | 0.75 |
| Results and discussion | 1.10 |
| Conclusion, limitations, ethics | 0.35 |
| References | 0.65 |

### I. Introduction

- Motivate scalable, repeated technical-interview practice for placement candidates without making unsupported failure-rate claims.
- Explain why static question banks and scarce human mocks provide limited personalization.
- Identify the risk of using an LLM as both content generator and evaluator.
- State the central design principle: **LLM generates; deterministic Python evaluates and adapts**.
- Define the scope as formative readiness support, not hiring prediction.
- List four concise contributions and preview the evaluation artifacts.
- End with the research questions: scoring agreement, guard robustness, adaptive traceability, and user usefulness. User usefulness **Needs empirical support.**

### II. Related Work

- Summarize AI mock-interview systems and evidence about realism/confidence.
- Cover LLM-based question generation and schema/quality-validation patterns.
- Review automated short-answer grading: lexical features, semantic embeddings, classifiers, and hybrid systems.
- Discuss limitations of LLM-as-judge approaches: variability, prompt sensitivity, and explainability.
- Introduce Elo/adaptive assessment and knowledge tracing as learner-state precedents.
- Contrast prior work with interViv’s strict generation/evaluation separation and guard-first validation.
- Finish with a comparison table: question generation, deterministic scoring, anti-gaming guard, learner model, role gaps, and deployment artifact.

### III. Proposed System

- Present the React → FastAPI → scoring/adaptive modules → PostgreSQL architecture.
- Describe resume-aware and company/role-aware session initialization.
- Specify the LLM JSON contract: question, reference answer, keywords, topic, difficulty, type, company, role, and follow-ups.
- Explain retry, 24-hour cache, per-minute rate limit, and structured fallback path.
- Show that the backend recomputes scoring server-side and does not trust client scores.
- Describe dashboard outputs and evidence traceability from round to recommendation.
- State production components: auth, database, Redis, Sentry, Docker, Render, and Vercel.

### IV. Methodology

- Define user/session state: selected skills, role, per-skill Elo, attempts, scores, concept mastery, weak areas, and prior questions.
- Give the implemented final-score formula and the four rubric dimensions.
- Describe the logistic-regression feature order and distinguish classifier metrics from system metrics.
- Specify guard rules and hard caps, including precedence over ordinary feedback.
- Define Elo question ratings, update equation, rating bounds, and difficulty thresholds.
- Explain adaptive priority: role gap → weakest learner skill → rotation fallback; then weak concepts.
- Provide question-tag schema and explain how ideal answer/keywords become deterministic references.
- Include pseudocode from Section 3 and an ablation plan for scoring components.

### V. Experiments

- **E1 classifier validation:** stratified held-out and five-fold results on 891 balanced rows.
- **E2 human agreement:** compare system scores/bands with three annotators on 30 answers; report κ, Pearson/Spearman, MAE, and confusion matrix.
- **E3 guard stress test:** invalid/adversarial categories and meaningful-short-answer false-positive checks.
- **E4 fallback audit:** schema validity, skill/difficulty coverage, duplicate rate, and LLM-failure recovery.
- **E5 adaptive trace test:** controlled learner states demonstrating target selection and difficulty changes.
- **E6 rapid usability pilot:** pre/post confidence and post-session usefulness if ethically cleared. **Needs empirical support.**
- Report hardware/runtime and software versions for reproducibility.

### VI. Results

- Report the classifier table without calling it platform “accuracy.”
- Report human baseline κ=0.642 and r=0.7392 with n=30, exact confidence intervals if recomputed, and error examples.
- Label 200-row persona findings as secondary simulation evidence only.
- Report guard caps and test outcomes, including false-positive checks for meaningful answers.
- Report question-bank coverage and any remaining audit warnings.
- If a pilot is completed, report paired pre/post and usability results with effect sizes and confidence intervals. **Needs empirical support.**
- Include negative results and disagreement cases, especially concise answers and question/answer mismatch.

### VII. Discussion

- Interpret what the preliminary agreement does and does not establish.
- Explain why deterministic evaluation improves repeatability and auditability but does not guarantee validity.
- Discuss trade-offs between lexical precision, semantic matching, and concise technically correct answers.
- Discuss how guard caps protect score validity and where they may create false positives.
- Explain why role profiles and dashboards are practice references rather than hiring criteria.
- Address privacy risks of resumes, audio, and optional camera-derived engagement.
- Present threats to internal, construct, and external validity.
- Identify future work: larger real-student study, expert-reviewed bank, fairness audit, and adaptive-strategy comparison.

### VIII. Conclusion

- Restate the guarded generation/evaluation separation.
- Summarize implemented platform capabilities in one sentence.
- State only the preliminary evidence actually reported.
- Avoid “replaces interviewers,” “predicts hiring,” or “proves readiness.”
- Close with the next validation step: a powered, multi-session student study with independent human ratings. **Needs empirical support.**

## 3. Adaptive engine specification

### State representation

| Scope | Variables to store |
|---|---|
| User identity | pseudonymous `user_id`; consent/version; target company/role; resume-derived skill tags; do not put raw PII in analytics tables |
| Per-skill state | current score, Elo, attempts, last-practiced timestamp, recent score window, uncertainty/confidence band |
| Per-concept state | concept ID, attempts, demonstrated count/rate, mastery level (`Untested`, `Weak`, or stronger state), last evidence timestamp |
| Session | session ID, selected skills, rounds per skill, total rounds, current round, status, current difficulty, asked-question IDs/text hashes |
| Round | skill, sub-domain, concept targets, question source, difficulty, question/context, answer text or de-identified hash, server word count, scoring components, guard result, final score, feedback, Elo before/after |
| Role gap | required level, importance weight, observed student level, tested flag, severity, per-skill readiness, rank score |
| Optional interaction | response time, WPM, pause count, optional engagement label/confidence, calibration state; keep separate from technical correctness |
| Provenance | scoring schema version, model artifact/hash, question-source mode, software release, timestamp |

### Candidate adaptivity strategies

| Strategy | Description | Advantages | Limitations | Recommendation |
|---|---|---|---|---|
| Rule-based rotation | Fixed A-A-A/B-B-B skill rotation with difficulty thresholds | Predictable, testable, cold-start safe | Limited personalization | Keep as fallback/control condition |
| Heuristic weak-area targeting | Choose highest weighted role gap or lowest observed skill; then weakest concepts | Interpretable and already implemented | Sensitive to sparse early evidence and hand-set thresholds | Primary near-term strategy |
| Elo difficulty | Treat an answer as a learner–item match and update per-skill rating | Lightweight online adaptation | Question ratings are coarse fixed values; score is continuous rather than binary | Keep, but report as Elo-style heuristic |
| Contextual bandit | Optimize question selection using expected learning gain/reward | Balances exploration and exploitation | Needs substantial interaction logs and careful reward definition | Later experiment |
| Supervised next-question model | Train from past trajectories to predict beneficial next skill/difficulty | Can model nonlinear patterns | Requires labeled outcomes and risks historical bias | Not justified with current data |
| Knowledge tracing | BKT/DKT-style latent mastery estimates per concept | Principled longitudinal learner model | Requires longer sequences and identifiability checks | Strong later-study direction |
| Reinforcement learning | Learn a policy for long-term improvement | Can optimize multi-step outcomes | Data hungry, difficult to validate, unsafe to claim now | Future work only |

### Implemented scoring and suggested reporting rubric

Implemented final score:

```text
base = 100 × (
    0.45 × semantic_or_lexical_match
  + 0.25 × classifier_component
  + 0.20 × keyword_coverage
  + 0.10 × tfidf_overlap
)

final_score = base + KG_bonus + NER_bonus - penalties
KG_bonus ≤ 4.0
NER_bonus = 0.4 per entity, maximum 5 entities
guard cap is applied as a hard upper bound
```

User-facing rubric dimensions are each 0–10:

- Correctness = 0.70 semantic + 0.30 classifier.
- Coverage = 0.45 keyword + 0.35 concept + 0.20 KG.
- Depth = 0.70 depth signal + 0.30 KG.
- Clarity = 0.45 structure + 0.40 clarity + 0.15 length fit.
- Weighted rubric = 0.35 correctness + 0.25 coverage + 0.20 depth + 0.20 clarity.

For analysis, the repository uses: Poor 0–30, Average 31–60, Good 61–100. Treat these as operational bands, not validated hiring thresholds.

Guard caps:

| Condition | Maximum score |
|---|---:|
| Empty | 5 |
| Gibberish | 10 |
| Repetition | 15 |
| Too short | 20 |
| Question parroting | 25 |
| Low-density filler | 30 |
| Keyword stuffing | 35 |
| Off-topic | configured by v2 guard; report actual returned cap |

Response time, WPM, pauses, self-reported confidence, and camera-derived engagement should be **analytics features only**, not inputs to technical correctness, until independently validated. A fast answer is not necessarily correct; a slow answer may reflect accessibility needs; facial expression does not establish engagement or competence.

### Elo and difficulty update

```text
question_rating = {easy: 1000, medium: 1500, hard: 2000}
expected = 1 / (1 + 10^((question_rating - elo_before)/400))
actual = final_score / 100
elo_after = clamp(elo_before + 32 × (actual - expected), 600, 2400)

if elo_after < 1200: difficulty = easy
elif elo_after < 1700: difficulty = medium
else: difficulty = hard
```

Example: a medium question at learner Elo 1200 has expected performance about 0.151. If the learner scores 70, the rating rises by approximately 17.6 points. This is an illustrative calculation, not participant evidence.

### Question-selection pseudocode

```text
INPUT: user_id, session_skills, target_role, rotation_skill,
       previous_difficulty, per_skill_elo, asked_questions

skill  ← rotation_skill
source ← "rotation"

IF authenticated(user_id) AND target_role exists:
    gaps ← compute_role_gaps(user_id, target_role)
    IF gaps has ranked weak areas:
        skill  ← highest_ranked_weak_area.skill
        source ← "gap_analysis"

IF source = "rotation" AND authenticated(user_id):
    candidates ← learner skills restricted to session_skills
    sort candidates by (untested first, then current_score ascending)
    IF candidates not empty:
        skill  ← candidates[0]
        source ← "skill_graph"

elo ← learner Elo for selected skill, else candidate session Elo
difficulty ← easy if elo < 1200
             medium if 1200 ≤ elo < 1700
             hard if elo ≥ 1700
             previous_difficulty if elo unavailable

concepts ← weak concepts sorted by demonstration rate ascending
append untested concepts alphabetically
target_concepts ← first two concepts

context ← {skill, difficulty, target_concepts, company, role,
           resume_skills, weak_skills, asked_questions[-8:]}

question ← cache lookup(context)
IF no usable cache entry:
    attempt schema-constrained LLM generation up to 3 times
IF generation fails or schema invalid:
    question ← structured CSV fallback matching context
IF no structured match:
    question ← deterministic template/legacy fallback

RETURN question and an explanation of source, skill, concepts, difficulty
```

### Feedback-generation template

```text
Overall: [performance band] — [one-sentence evidence summary]

Strengths
- Correctly explained: [covered concept 1]
- Used relevant evidence/terminology: [keyword/entity/example]

Needs improvement
- Missing or unclear: [missing concept 1]
- Reasoning issue: [depth/structure/guard-specific explanation]

Next answer structure
1. Define [core concept].
2. Explain how/why it works.
3. Give one concrete example or trade-off.
4. State complexity, limitation, or edge case where relevant.

Suggested resources
- [official documentation or reviewed course section for missing concept]
- [one targeted practice question at selected difficulty]

Next question rationale
- Selected [skill/concept] because [role gap / low score / untested concept].
```

Resource links should come from a reviewed whitelist, not arbitrary model-generated URLs.

## 4. Evaluation plan

### Research questions

- **RQ1:** How closely do deterministic interViv scores agree with independent human ratings?
- **RQ2:** How reliably do guard rules cap invalid/gamed answers without flagging meaningful answers?
- **RQ3:** Does the adaptive selector choose traceable weak-skill/weak-concept questions under controlled learner states?
- **RQ4:** Do students perceive the platform, feedback, and roadmap as useful, fair, and realistic? **Needs empirical support.**
- **RQ5:** Does repeated use improve answer quality, confidence, or weak-skill performance? **Needs empirical support.**

### Minimal realistic evaluation before a near-term deadline

Use existing quantitative evidence as the core and add a small pilot only if consent and institutional approval/exemption are already in place.

**A. Artifact evaluation (must do):**

- Reproduce classifier held-out and five-fold metrics on 891 rows.
- Recompute the 30-answer human baseline with Pearson and Spearman correlation, MAE, 95% bootstrap confidence intervals, weighted κ or band agreement, and confusion matrix.
- Audit questionable baseline rows; report both full-set and sensitivity analysis if exclusions are justified before looking at results.
- Run guard categories with at least 10 examples each: empty, random tokens, keyboard spam, repetition, parroting, filler, off-topic, stuffing, concise-correct, and normal detailed.
- Demonstrate at least six controlled adaptive traces spanning low/medium/high Elo, role gap, weakest skill, weak concept, cold start, and LLM failure fallback.
- Run and report the full test suite (currently 116 passing).

**B. Exploratory usability pilot (only if permitted):**

- **N:** 12–20 convenience-sampled placement-preparing students; state that this is an exploratory pilot, not a powered effectiveness trial.
- **Duration:** 25–35 minutes per participant.
- **Tasks:** consent/pre-survey (5 min), one 6–9-question session across 2–3 skills (15–20 min), inspect dashboard/roadmap (5 min), post-survey (5 min).
- **Logged metrics:** completion, per-round score, component scores, difficulty, Elo, response time, guard flags, target concepts, question source, errors, and System Usability Scale-style items.
- **Analysis:** medians/IQRs and means/SDs; paired change with exact Wilcoxon or paired t-test only as exploratory; effect size and confidence interval; no causal language.
- A claim that one session improves readiness **Needs empirical support.**

### Stronger later evaluation

- Recruit at least 40 completers for a paired pre/post study intended to detect a standardized mean change around d=0.5; recruit ~47 allowing 15% attrition.
- Prefer 60–100 participants if comparing adaptive and nonadaptive conditions or analyzing subgroups.
- Randomize participants to adaptive vs fixed/rotation-only sequencing, or use a counterbalanced crossover design.
- Run 2–3 sessions over 1–2 weeks to observe longitudinal change rather than same-session familiarity.
- Use unseen, expert-reviewed pre/post question sets matched for skill and difficulty.
- Blind at least two independent raters to system score, condition, and time point; adjudicate disagreements.
- Pre-register primary outcomes, exclusions, and analysis; freeze the scoring model before data collection.
- Primary outcome: blinded human-rated answer quality or matched knowledge score; secondary outcomes: confidence, usefulness, score trend, weak-concept reduction, time, and completion.
- Compare guard false-positive/false-negative rates and score calibration across language/background groups only when sample sizes and consent permit.

### Objective metrics

- Pre/post expert-scored technical-answer total on matched forms.
- System–human Pearson and Spearman correlations, MAE/RMSE, and band confusion matrix.
- Mean/median final score and four rubric dimensions.
- Accuracy or concept coverage on repeated weak-skill items.
- Difficulty progression: proportion easy/medium/hard by round and appropriate transitions.
- Elo change by skill, reported as system state rather than ground-truth ability.
- Response time, WPM, pauses, completion, abandonment, API error, and fallback rate.
- Guard trigger rate and false-positive/false-negative rates on labeled adversarial cases.
- Question-quality ratings: correctness, relevance, clarity, difficulty fit, duplication, and schema validity.

### Subjective metrics

- Realism of questions and interview flow.
- Usefulness, specificity, clarity, and actionability of feedback.
- Perceived fairness and consistency of scoring.
- Trust in the explanation and next-question rationale.
- Confidence explaining technical ideas aloud.
- Perceived readiness for the target role.
- Cognitive load, anxiety, and willingness to reuse/recommend.

### Statistical tests

- Paired t-test for a single approximately symmetric pre/post continuous outcome; report mean difference, 95% CI, p, and paired Cohen’s dz.
- Wilcoxon signed-rank test for ordinal Likert composites, skewed differences, or small samples; report median difference and rank-biserial correlation.
- Spearman correlation in addition to Pearson for system–human agreement.
- Cohen’s or weighted κ for categorical/ordinal agreement; Fleiss κ if more than two raters with common categories.
- McNemar test for paired binary outcomes; Stuart–Maxwell for paired multi-category transitions if sample size permits.
- Mixed-effects model for repeated rounds/sessions, with participant random intercept, in a stronger study.
- Bootstrap confidence intervals when distributional assumptions are doubtful.
- With a very small N, emphasize descriptive statistics and individual trajectories; do not turn “not significant” into “no effect.”

### Illustrative sample-size targets

For a two-sided paired test with α=0.05 and 80% power, the normal approximation is:

```text
n ≈ ((1.96 + 0.84) / d)^2
```

| Assumed paired standardized effect d | Approximate completers | Recruit with 15% attrition |
|---:|---:|---:|
| 0.50 | 32 | 38 |
| 0.40 | 49 | 58 |
| 0.30 | 88 | 104 |

These are planning illustrations, not a substitute for G*Power/R simulation using the selected primary outcome, expected correlation, design, and attrition.

### Ready-to-use Google Form survey (18 questions)

Use a pseudonymous participant code. Do not collect email automatically unless separately consented.

**Section A — Eligibility and consent**

1. **Consent** — Multiple choice, required: “I have read the study information and agree to participate.” Options: Yes / No (No ends form).
2. **Age eligibility** — Multiple choice: 18 or older / Under 18 (exclude unless approved minor protocol exists).
3. **Current stage** — Multiple choice: Undergraduate year 1/2/3/4+; postgraduate; recent graduate; other.
4. **Interview experience** — Multiple choice: None; 1–2; 3–5; 6+ technical interviews/mocks.
5. **Primary target role** — Dropdown: Software engineer; data analyst; data scientist/ML; cloud/backend; frontend; other/prefer not to say.

**Section B — Pre-session (1=Strongly disagree, 5=Strongly agree)**

6. I feel confident explaining technical concepts aloud.
7. I can structure an answer with definition, reasoning, and an example.
8. I feel prepared for technical questions for my target role.
9. I can identify which technical concepts I need to improve.
10. Technical interview practice makes me anxious. *(reverse/independent construct)*

**Section C — Immediate post-session (1=Strongly disagree, 5=Strongly agree)**

11. The questions were relevant to my selected skills and target role.
12. The sequence and difficulty of questions felt appropriate.
13. The feedback clearly identified what I did well.
14. The feedback clearly identified what I should improve.
15. The scoring explanation felt consistent with my answers.
16. The dashboard and roadmap gave me actionable next steps.
17. After this session, I feel more confident explaining technical concepts aloud. **Needs empirical support.**
18. I would use interViv again for interview preparation.

Add two optional unnumbered text prompts if the form can exceed 18 items:

- “What was the most useful part of the session, and why?”
- “Describe one question, score, or feedback message that felt inaccurate or unfair.”

For a true pre/post comparison, repeat items 6–10 after the session using identical wording; analyze matched pairs. Do not infer change by comparing item 17 alone.

## 5. Results and analysis templates

### Table A — Participant characteristics

| Characteristic | Category/statistic | n (%) or mean ± SD |
|---|---|---:|
| Participants | Included / enrolled | [PLACEHOLDER] |
| Study stage | UG / PG / graduate | [PLACEHOLDER] |
| Prior interviews | Median (IQR) | [PLACEHOLDER] |
| Target role | Categories | [PLACEHOLDER] |
| Sessions completed | Mean ± SD | [PLACEHOLDER] |

### Table B — Pre/post comparison

| Outcome (scale) | N | Pre mean ± SD | Post mean ± SD | Mean/median change | 95% CI | Test | p | Effect size |
|---|---:|---:|---:|---:|---:|---|---:|---:|
| Technical score (0–100) | [P] | [P] | [P] | [P] | [P] | Paired t/Wilcoxon | [P] | [P] |
| Explanation confidence (1–5) | [P] | [P] | [P] | [P] | [P] | Wilcoxon | [P] | [P] |
| Perceived readiness (1–5) | [P] | [P] | [P] | [P] | [P] | Wilcoxon | [P] | [P] |

Any improvement statement from this table **Needs empirical support.**

### Table C — Automated scoring validation

| Evaluation | N | Metric | Estimate | 95% CI | Interpretation |
|---|---:|---|---:|---:|---|
| Classifier held-out | 179 | Accuracy | 0.9553 | [recompute] | Classifier only |
| Classifier 5-fold | 891 | Accuracy | 0.9562 ± 0.0148 | [recompute] | Internal CV |
| Human baseline | 30 | Pearson r | 0.7392 | [bootstrap] | Preliminary agreement |
| Human baseline | 30 | Mean κ | 0.642 | [bootstrap] | Three-rater band agreement |

### Table D — Guard evaluation

| Input category | Labeled cases | Correctly capped | False negatives | Meaningful answers falsely capped | Cap(s) |
|---|---:|---:|---:|---:|---|
| Empty/whitespace | [P] | [P] | [P] | — | 5 |
| Gibberish/spam | [P] | [P] | [P] | — | 10–15 |
| Too short | [P] | [P] | [P] | [P] | 20 |
| Parroting/filler | [P] | [P] | [P] | [P] | 25–30 |
| Keyword stuffing | [P] | [P] | [P] | [P] | 35 |
| Concise-correct controls | [P] | — | — | [P] | none expected |

### Recommended charts

- Grouped bar chart: post-session usefulness/fairness/realism distributions; x-axis item, y-axis percentage, legend 1–5 Likert.
- Participant paired-dot or slope chart: pre vs post technical score; avoid a bar chart that hides individual variation.
- Line chart: mean final score by round with 95% CI; x-axis round, y-axis score, separate adaptive/control lines only in a controlled study.
- Stacked area/bar: easy/medium/hard question proportion by round.
- Scatter plot: human mean vs system score with identity line, regression line, r, Spearman ρ, and N.
- Confusion matrix: human band vs system band with raw counts and row-normalized percentages.
- Guard bar chart: true-positive and false-positive rates by invalid-answer category.

### Python/pandas/SciPy analysis pseudocode

```python
import numpy as np
import pandas as pd
from scipy import stats

df = pd.read_csv("participant_results.csv")
paired = df.dropna(subset=["pre_score", "post_score"]).copy()

summary = paired[["pre_score", "post_score"]].agg(["count", "mean", "std"])
diff = paired["post_score"] - paired["pre_score"]

mean_change = diff.mean()
sd_change = diff.std(ddof=1)
cohens_dz = mean_change / sd_change if sd_change else np.nan

# Use after inspecting the distribution of paired differences.
t_stat, p_t = stats.ttest_rel(
    paired["post_score"], paired["pre_score"], nan_policy="omit"
)
w_stat, p_w = stats.wilcoxon(diff, alternative="two-sided", zero_method="wilcox")

# Normal-approximation 95% CI for mean paired change.
se = sd_change / np.sqrt(len(diff))
t_crit = stats.t.ppf(0.975, df=len(diff) - 1)
ci = (mean_change - t_crit * se, mean_change + t_crit * se)

print(summary)
print({"mean_change": mean_change, "ci95": ci,
       "paired_t": (t_stat, p_t), "wilcoxon": (w_stat, p_w),
       "cohens_dz": cohens_dz})

# System–human agreement.
ratings = pd.read_excel("human_baseline_real_combined.xlsx")
pearson = stats.pearsonr(ratings["system_score"], ratings["ann_mean"])
spearman = stats.spearmanr(ratings["system_score"], ratings["ann_mean"])
mae = np.mean(np.abs(ratings["system_score"] - ratings["ann_mean"]))
```

## 6. Related-work starter list

Use IEEE numbering in the final manuscript and verify metadata against Crossref/DBLP/ACL before camera-ready submission. Preprints are identified explicitly.

1. N. Gomez, S. S. Batham, M. Volonte, and T. D. Do, [“Virtual Interviewers, Real Results: Exploring AI-Driven Mock Technical Interviews on Student Readiness and Confidence,”](https://arxiv.org/abs/2506.16542) arXiv:2506.16542, 2025. A formative study with 20 CS students; useful for motivation, realism, confidence, and pilot design. *(Preprint.)*
2. J. S. Cheon, H. K. Jang, J. H. Kim, B. M. Bae, D. G. Lee, and I. Y. Moon, [“A Study on the Design and Implementation of an AI Mock Interview System for Computer Science Interview Preparation Using LLM-based ChatGPT,”](https://doi.org/10.14702/JPEE.2024.643) Journal of Practical Engineering Education, vol. 16, no. 5, pp. 643–651, 2024. Combines LLM prompts, speech-to-text, and real-time feedback for CS interview practice.
3. A. Panfilova et al., [“The AI interviewer: multi-faceted evaluation of adaptive questioning by large language models,”](https://doi.org/10.1038/s41598-026-46517-7) Scientific Reports, 2026. Provides a rigorous rubric and schema-compliance evidence for adaptive follow-up behavior; it does not validate technical-answer scoring.
4. S. S. Mucciaccia et al., [“Automatic Multiple-Choice Question Generation and Evaluation Systems Based on LLM: A Study Case With University Resolutions,”](https://aclanthology.org/2025.coling-main.154/) in Proc. COLING, pp. 2246–2260, 2025. Supports constrained generation followed by independent quality evaluation.
5. S. Haller, A. Aldea, C. Seifert, and N. Strisciuglio, [“Survey on Automated Short Answer Grading with Deep Learning: from Word Embeddings to Transformers,”](https://arxiv.org/abs/2204.03503) arXiv:2204.03503, 2022. Finds that semantic representations and engineered features are often complementary. *(Preprint.)*
6. G. Meyer, P. Breuer, and J. Fürst, [“ASAG2024: A Combined Benchmark for Short Answer Grading,”](https://arxiv.org/abs/2409.18596) arXiv:2409.18596, 2024. Combines seven datasets and highlights generalization and human-performance gaps. *(Preprint.)*
7. N. Reimers and I. Gurevych, [“Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks,”](https://aclanthology.org/D19-1410/) in Proc. EMNLP-IJCNLP, pp. 3982–3992, 2019. Establishes efficient sentence embeddings and cosine similarity used by semantic-scoring approaches.
8. R. Pelánek, [“Applications of the Elo rating system in adaptive educational systems,”](https://doi.org/10.1016/j.compedu.2016.03.017) Computers & Education, vol. 98, pp. 169–179, 2016. Reviews Elo-style learner/item updating and its strengths and limitations in adaptive education.
9. A. T. Corbett and J. R. Anderson, [“Knowledge tracing: Modeling the acquisition of procedural knowledge,”](https://doi.org/10.1007/BF01099821) User Modeling and User-Adapted Interaction, vol. 4, no. 4, pp. 253–278, 1995. Foundational Bayesian knowledge-tracing model for latent skill mastery.
10. C. Piech et al., [“Deep Knowledge Tracing,”](https://proceedings.neurips.cc/paper/2015/hash/bac9162b47c56fc8a4d2a519803d51b3-Abstract.html) Advances in Neural Information Processing Systems 28, 2015. Introduces recurrent models for longitudinal student knowledge; appropriate as future-work context, not as a description of interViv’s current heuristic mastery model.

Suggested related-work synthesis: prior systems demonstrate the feasibility of AI mock interviews and adaptive questioning; ASAG literature motivates hybrid semantic and engineered scoring; Elo and knowledge tracing motivate learner-state updates. interViv’s narrower novelty is the operational separation of generative questions from deterministic, guarded assessment inside a full readiness workflow.

## 7. Provisional writing support

### Provisional abstract (183 words)

**Provisional—replace bracketed fields and retain only verified results.**

Technical-interview practice platforms increasingly use large language models to generate questions and evaluate candidate responses, but combining both functions in one model can make assessment difficult to reproduce and audit. This paper presents interViv, an adaptive interview-readiness platform that enforces a strict architectural boundary: a language model generates schema-constrained questions and reference material, while deterministic Python modules score answers, apply anti-gaming caps, update per-skill learner state, and recommend subsequent practice. The platform integrates resume-aware skill selection, company/role reference profiles, semantic and lexical evidence, a logistic-regression answer-quality component, knowledge-graph and entity signals, Elo-style difficulty adaptation, concept mastery, gap analysis, and personalized roadmaps. The current artifact contains a balanced 891-example classifier dataset, a 2,319-row interview dataset, a 53-question structured fallback bank, and a 30-answer human-rated baseline. Preliminary evaluation reports classifier-only validation accuracy of 0.9553 and system–human score correlation of 0.7392 on the small baseline; these values do not represent hiring or whole-system accuracy. **Needs empirical support.** Guard stress tests and 116 automated tests provide additional implementation evidence. Future work will evaluate learning, fairness, and usability with a larger real-student study.

### Provisional introduction draft (277 words)

**Provisional—edit venue framing, citations, and any empirical claim before submission.**

Technical interviews require candidates not only to recall concepts but also to explain assumptions, trade-offs, examples, and edge cases under time pressure. Students can develop these skills through repeated mock interviews, yet access to experienced interviewers is limited and static question banks provide little guidance about what to practice next. Recent large language models make it possible to generate varied, role-relevant questions and follow-ups, but a system that also asks the same model to judge candidate quality inherits problems of response variability, prompt sensitivity, opaque criteria, and difficult-to-audit feedback. These concerns are especially important when a score may affect a learner’s confidence or preparation decisions.

interViv is an interview-readiness platform designed around a deliberate separation of responsibilities. The language model is restricted to generating a structured question, ideal answer, keywords, and follow-ups; it is not permitted to score, grade, recommend hiring, or determine readiness. Candidate responses are evaluated by a deterministic pipeline combining semantic or lexical match, a trained logistic-regression component, keyword and TF-IDF evidence, knowledge-graph coverage, named technical entities, and explicit anti-gaming caps. Persistent per-skill Elo ratings, concept-mastery evidence, and target-role gaps then guide the next difficulty and topic. The same evidence is exposed through a dashboard and deterministic learning roadmap.

This paper investigates whether such a guarded architecture can provide reproducible, explainable practice signals while retaining the variety of generative questions. We describe the full-stack system, scoring contract, adaptive selector, fallback behavior, and privacy boundary, and report preliminary classifier, human-agreement, guard, and software-verification evidence. Claims that interViv improves technical knowledge, confidence, or placement outcomes **Needs empirical support.** The intended contribution is therefore a transparent formative-practice architecture and research artifact, not an automated hiring decision system.

## 8. Figures and appendix plan

### Figure 1 — System architecture

**What to show:** User/browser → React interview UI → FastAPI routes → question runtime and deterministic scoring → learner analytics → PostgreSQL; external LLM connected only to question runtime; Redis/Sentry as production services.

**Exact labels:** `Resume / Voice / Text`, `React 18 + Vite`, `FastAPI`, `JWT Auth`, `Question Runtime`, `LLM: Question + Reference Only`, `CSV/Template Fallback`, `Answer Guard`, `Deterministic Scoring`, `Skill Graph`, `Concept Mastery`, `Gap Analysis`, `Roadmap`, `PostgreSQL`, `Redis Cache + Rate Limit`, `Dashboard Evidence`.

**Caption:** **Fig. 1. interViv architecture and trust boundary. The LLM generates structured practice content only; all scoring, guards, learner-state updates, gap calculations, and recommendations are deterministic.**

### Figure 2 — Adaptive question-selection flow

**What to show:** cold start/rotation; role-gap priority; weakest-skill fallback; weak/untested concepts; Elo thresholds; cache/LLM/fallback; scoring and state update loop.

**Exact decision labels:** `Target role selected?`, `Ranked gap available?`, `Observed skill state available?`, `Elo < 1200`, `1200 ≤ Elo < 1700`, `Elo ≥ 1700`, `Weak concepts?`, `Schema-valid LLM response?`.

**Caption:** **Fig. 2. Deterministic adaptive-selection flow. Role gaps and learner evidence select the skill and concepts; Elo thresholds select difficulty; generation failure routes to a structured fallback bank.**

### Figure 3 — Traceable sample round/transcript

**What to show:** anonymized question, candidate answer excerpt, question source, target concepts, four rubric dimensions, covered/missing concepts, guard status, Elo before/after, feedback, next-question rationale.

**Exact labels:** `Question Source`, `Target Skill`, `Target Concepts`, `Difficulty`, `Correctness (0–10)`, `Coverage (0–10)`, `Depth (0–10)`, `Clarity (0–10)`, `Guard Cap`, `Final Score (0–100)`, `Elo Before`, `Elo After`, `Next Target`.

**Caption:** **Fig. 3. Example evidence trace for one anonymized interview round, linking question context and deterministic scoring components to feedback and the next adaptive target.**

### Figure 4 — Validation results

**What to show:** preferably a two-panel figure: (a) human mean vs system score scatter with identity/regression lines; (b) human-band × system-band confusion matrix. If a pilot exists, replace or add paired pre/post slopes. **Needs empirical support.**

**Exact labels:** Panel A x-axis `Human Mean Score (0–100)`, y-axis `System Score (0–100)`, annotation `Pearson r = 0.7392; N = 30`; Panel B axes `Human Band` and `System Band`, categories `Poor (0–30)`, `Average (31–60)`, `Good (61–100)`.

**Caption:** **Fig. 4. Preliminary system–human agreement on 30 answers rated by three annotators. The small baseline supports calibration analysis but not replacement-level or hiring-validity claims.**

### Appendix/supplementary items

- Full 18-item survey, consent text, and participant information sheet.
- Question JSON schema and two valid/invalid examples.
- Adaptive-selection and Elo pseudocode.
- Scoring formula, rubric mapping, model feature order, and schema version.
- Complete guard taxonomy, thresholds, caps, and labeled test cases.
- Question tag dictionary: skill, sub-domain, topic, difficulty, type, company, role, keywords, follow-ups.
- Human-rater rubric and adjudication procedure.
- Dataset/model cards with provenance, hashes, class balance, exclusions, and intended use.
- Additional confusion matrices, bootstrap intervals, error cases, and ablations.
- Deployment/reproduction commands and environment lock.

## 9. Six conference-writing and submission tips

1. Lead with one defensible novelty: the **LLM-generation/deterministic-assessment boundary**; do not present every feature as a separate novelty.
2. Use “preliminary,” “formative,” and “readiness support” precisely; never convert classifier accuracy into system accuracy or employment prediction.
3. Keep the main paper to six pages until ICONAT resolves its inconsistent public page-limit wording; use the official IEEE conference template and remove all template guidance text.
4. Because review is single-blind, author names are normally visible; follow the live CMT instructions rather than anonymizing automatically.
5. Put equations, thresholds, N, confidence intervals, effect sizes, negative cases, and data provenance beside each claim; every improvement claim **Needs empirical support.**
6. Before upload, verify title/author order, references/DOIs, figure readability at column width, PDF fonts, plagiarism/originality, CMT subject area, PDF eXpress requirements, registration, and copyright steps.

## 10. Submission deliverables checklist

- [ ] Verified ICONAT deadline and live CMT submission link.
- [ ] Final concise title aligned with the Machine Learning, Cloud and Data Analytics track.
- [ ] 150–190 word self-contained abstract with no unsupported claims.
- [ ] 3–5 keywords.
- [ ] Six-page IEEE two-column manuscript PDF, or confirmed organizer-approved length.
- [ ] Editable Word or LaTeX source using the official IEEE conference template.
- [ ] Final author names, affiliations, emails, ORCIDs, and corresponding author.
- [ ] CMT title, abstract, co-authors, conflicts, subject areas, and answers to submission questions.
- [ ] Four publication-quality figures with readable labels and captions.
- [ ] Final tables with N, metrics, confidence intervals, and effect sizes.
- [ ] Verified IEEE-style bibliography and DOI/URL metadata.
- [ ] Ethics approval/exemption, consent materials, and data-management statement if participants are used.
- [ ] De-identified analysis dataset and reproducible scripts, if permitted.
- [ ] Code/model/data availability and limitations statements.
- [ ] AI-use disclosure if required by the venue/institution; authors remain responsible for all content.
- [ ] Plagiarism/originality and grammar checks.
- [ ] PDF font embedding, page-size, margin, and figure-resolution checks.
- [ ] PDF eXpress compliance after acceptance, if instructed.
- [ ] Author registration/payment and presenter designation after acceptance.
- [ ] IEEE copyright form after acceptance.
- [ ] Camera-ready source/PDF and supplementary material.
- [ ] 12-minute presentation plus 3-minute Q&A, subject to final program guidance.

## 11. Immediate priority order

1. Verify whether CMT still accepts papers and resolve the June 20/July 10 conflict.
2. Freeze the research claim and scoring artifact; do not make last-minute model changes after evaluation.
3. Recompute the 30-answer baseline with confidence intervals and audit questionable row alignment.
4. Create a six-page draft using Figures 1, 2, and 4 plus two compact tables.
5. Run a student pilot only if ethical permission and recruitment are already available; otherwise label it future work.
6. Complete author metadata, references, template compliance, and submission checks.
