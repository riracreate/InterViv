# Research Positioning

interViv is a company-style, role-style, resume-aware adaptive mock interview
platform for students. Its research story is deliberately narrow and defensible:

```text
LLM = question and reference generation only
Python = answer scoring, feedback, guardrails, adaptivity, dashboards
```

This separation is the project's core credibility claim. It lets interViv use
modern question generation while avoiding LLM-as-judge scoring randomness.

## Research Claim

Students preparing for placements need repeated, role-aligned interview
practice with concrete feedback. interViv addresses this by combining:

- company-style and role-style question targeting
- resume-aware skill selection
- adaptive difficulty and weak-concept targeting
- deterministic scoring and anti-gibberish caps
- dashboards, gap analysis, and roadmaps

## Relevant Literature

Use these citations as direct support for the report/thesis narrative.

### AI Mock Interviews

Gomez et al. study AI-driven mock technical interviews with 20 CS students and
report that participants found the experience realistic and useful for
confidence-building, while also noting issues with conversational flow and
timing. This supports interViv's motivation and suggests a practical pre/post
student study design.

Source: [Virtual Interviewers, Real Results: Exploring AI-Driven Mock Technical Interviews on Student Readiness and Confidence](https://arxiv.org/abs/2506.16542)

### LLM Question Generation

Mucciaccia et al. present a COLING 2025 pipeline for LLM-based multiple-choice
question generation and evaluation. The relevant design lesson for interViv is
not MCQs specifically; it is the generation-plus-validation pattern: generate
questions under constraints, then audit quality separately.

Source: [Automatic Multiple-Choice Question Generation and Evaluation Systems Based on LLM](https://aclanthology.org/2025.coling-main.154/)

### Adaptive Interview Orchestration

Panfilova et al. evaluate large language models as adaptive interviewers in
semi-structured interviews. This is not a technical-placement paper, so use it
carefully. It supports follow-up orchestration and standardized interviewer
behavior, not answer scoring.

Source: [The AI interviewer: multi-faceted evaluation of adaptive questioning by large language models](https://www.nature.com/articles/s41598-026-46517-7)

## How interViv Differs

Many AI-interview systems let an LLM score, judge, or summarize candidate
quality. interViv should not make that move. The stronger positioning is:

- LLM-generated prompts create variety and role relevance.
- Deterministic scoring keeps the assessment reproducible.
- Guard caps protect the score from random text, keyboard spam, and keyword
  stuffing.
- Learning analytics convert scoring evidence into next actions.

## System Contributions

The project can be presented as four contributions:

1. A constrained LLM question-generation pipeline that outputs structured
   question JSON and falls back to a curated bank.
2. A deterministic open-answer scoring pipeline with anti-gibberish and
   anti-gaming caps.
3. A student learner model that tracks skills, concepts, weak areas, and target
   role gaps.
4. A dashboard and roadmap layer that turns interview performance into
   actionable preparation steps.

## Evaluation Plan

A strong 30-student study is enough for a credible final-year project report.

### Participants

Recruit 20-30 students preparing for internships or placements.

### Protocol

1. Pre-survey:
   - confidence in technical interviews
   - confidence explaining solutions aloud
   - perceived readiness for target role
   - anxiety level
2. Each participant completes 2-3 interViv sessions.
3. Post-survey:
   - same confidence/readiness questions
   - perceived usefulness of feedback
   - perceived fairness of deterministic scoring
   - usefulness of dashboard and roadmap
4. Optional qualitative interview:
   - what feedback was most actionable
   - where questions felt unrealistic
   - what should change before real placement prep

### Metrics

- change in self-rated confidence
- change in perceived readiness
- completion rate
- average score trend across sessions
- weak-skill improvement across repeated attempts
- qualitative themes about fairness and usefulness

## What To Avoid Claiming

Avoid overstated claims like:

- "interViv predicts hiring success"
- "interViv replaces human interviewers"
- "LLM evaluates candidate quality"
- "company profiles are exact recruiter rubrics"

Use safer claims:

- "interViv supports interview readiness practice"
- "interViv provides deterministic feedback signals"
- "company profiles are curated practice references"
- "dashboards help students identify weak skills and next actions"

## Near-Term Engineering Roadmap

1. Keep scoring modules stable, but document their rubric mapping.
2. Run `scripts/question_audit.py` before demos or dataset changes.
3. Add dashboard panels for user-vs-target-role and progress over time.
4. Store more per-dimension scores for longitudinal analysis.
5. Run the student pre/post study and write findings in a 4-6 page report.
