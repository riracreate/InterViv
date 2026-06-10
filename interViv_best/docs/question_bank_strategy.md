# Question Bank Strategy

interViv uses LLMs only to generate interview questions and reference material.
The LLM never scores, judges, evaluates, or produces feedback for a candidate
answer.

## Structured Fallback Schema

The deterministic fallback bank lives at `data/fallback_question_bank.csv` with
this schema:

```text
company,role,skill,sub_domain,topic,difficulty,question_type,question,ideal_answer,ideal_keywords,followups
```

The current seed has 53 questions covering:

- DSA
- DBMS
- OS
- CN
- OOP
- Python
- JavaScript
- React
- Node.js
- FastAPI
- System Design
- HR / Behavioral

## Filtering Priority

Question selection prefers:

1. selected company
2. selected role
3. selected skill and sub-domain from resume/session state
4. weak skills and target concepts from deterministic skill graph/mastery
5. adaptive difficulty from Elo
6. structured fallback bank
7. legacy CSV/domain/template fallback

For authenticated users, saved company/role targets are read from the user
record. For anonymous or one-off sessions, the selected company/role is carried
on the session start request. Resume skills come from the candidate document and
weak concepts come from deterministic skill graph / concept mastery state.

The company practice graph now covers:

- TCS
- Infosys
- Accenture
- Wipro
- Amazon
- Microsoft
- Google
- Meta

## LLM Prompt Shape

When an LLM provider is configured, the prompt requires strict JSON:

```json
{
  "question": "...",
  "ideal_answer": "...",
  "ideal_keywords": ["...", "..."],
  "sub_domain": "...",
  "topic": "...",
  "difficulty": "easy|medium|hard",
  "question_type": "conceptual|coding|system_design|behavioral|resume_based",
  "company": "...",
  "role": "...",
  "followups": ["...", "..."]
}
```

The prompt explicitly forbids scoring, judging, grading, evaluating,
pass/fail decisions, hiring decisions, and answer feedback.

## Deterministic Scoring Boundary

The backend stores `ideal_answer` and `ideal_keywords` from the LLM or fallback
bank as reference material. The scoring pipeline then deterministically runs:

- answer guard
- 3-layer NLP scorer
- classifier signal
- knowledge graph
- NER
- rule-based feedback

No LLM output is used as an answer score or judge.
