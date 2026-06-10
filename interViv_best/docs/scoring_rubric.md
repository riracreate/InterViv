# interViv Scoring Rubric

interViv scores candidate answers with deterministic Python. The LLM is used
only to generate interview questions, reference answers, expected keywords,
topic metadata, and follow-up prompts. It does not score answers, judge
candidates, decide readiness, or produce answer feedback.

## Runtime Pipeline

```text
candidate answer
  -> answer guard
  -> NLP / lexical / semantic feature extraction
  -> answer-quality classifier signal
  -> knowledge-graph concept coverage
  -> entity extraction
  -> deterministic feedback
  -> final score with guard cap applied
```

The backend entry point is `backend/scoring/pipeline.py`. The answer route
calls it from `backend/routes/answer.py` when a candidate submits a round.

## Guard Caps

`modules/answer_guard.py` runs before normal scoring. If it flags the answer,
the final score can never exceed the guard cap.

| Guard reason | Maximum score | Meaning |
| --- | ---: | --- |
| `empty` | 5 | Empty or whitespace-only answer. |
| `gibberish` | 10 | Random text, keyboard spam, nonsense tokens, abnormal character/vowel patterns. |
| `repetition` | 15 | Repeated meaningless text or one token dominating the answer. |
| `too_short` | 20 | Not enough explanation to evaluate fairly. |
| `question_parroting` | 25 | Mostly repeats the question instead of answering it. |
| `low_density` | 30 | Long enough, but mostly generic filler. |
| `off_topic` | 30 | Does not address the question. |
| `keyword_stuffing` | 35 | Lists expected keywords without meaningful explanation. |

User-facing guard feedback:

```text
Your answer looks incomplete or gibberish. Please write a meaningful explanation.
```

## Rubric Dimensions

The dashboard should present these as interpretable scoring dimensions, not as
an opaque single score.

| Dimension | Source fields | What it means |
| --- | --- | --- |
| Content match | `layer1_score`, `tfidf_score`, `semantic_score`, `semantic_component_source` | How closely the answer matches the reference answer and expected topic. |
| Keyword coverage | `keyword_coverage`, `keyword_coverage_details` | Whether expected technical terms or phrases are covered in context. |
| Concept coverage | `kg_score`, `covered_concepts`, `missing_concepts`, `kg_label` | Whether the answer demonstrates knowledge-graph concepts for the skill. |
| Answer quality | `layer2_score`, `depth_score`, `structure_score`, `clarity_score`, `accuracy_score` | Whether the answer is structured, clear, and sufficiently deep. |
| Classifier signal | `svm_label`, `classifier_confidence`, `classifier_probabilities` | Deterministic ML classifier estimate of answer quality. |
| Guard quality | `guard_applied`, `guard_caps`, `guards_fired` | Anti-gaming result and hard cap evidence. |

## Score Bands

These bands are for reporting and dashboards. They do not replace the numeric
score.

| Final score | Band | Interpretation |
| ---: | --- | --- |
| 75-100 | Strong | Answer covers the expected concepts with enough detail and structure. |
| 50-74 | Developing | Partially correct answer; missing concepts or depth should be reviewed. |
| 21-49 | Weak | Low match to expected concepts, thin explanation, or major omissions. |
| 0-20 | Invalid / incomplete | Empty, gibberish, too short, or not enough signal for normal scoring. |

## Feedback Rules

`modules/c4_feedback.py` should keep feedback tied to deterministic evidence:

- name missing concepts from `missing_concepts`
- name missing keywords from `keyword_coverage_details`
- mention guard reason when a guard fired
- suggest the next topic from missing concepts, weak skills, or follow-ups
- avoid unsupported hiring decisions, pass/fail labels, or LLM-style judging

## Why This Is Paper-Friendly

This structure gives interViv a clear and reproducible assessment story:

- LLM output is constrained to question/reference generation.
- Candidate scoring is deterministic and explainable.
- Every dashboard claim can be traced to stored scoring fields.
- Guard caps prevent random or meaningless text from receiving normal scores.
