# Per-guard feedback. Each entry overrides the full feedback payload so the
# candidate sees a message that names the actual failure mode (not the
# generic "review core concepts" that SVM-Poor used to produce).
_GUARD_FEEDBACK = {
    "empty": {
        "headline":    "Your answer was empty.",
        "weakness":    "No content to evaluate. Even a brief attempt scores higher than nothing.",
        "improvement": "Speak or type at least 2-3 sentences explaining the concept.",
    },
    "gibberish": {
        "headline":    "We couldn't make sense of your answer.",
        "weakness":    "The text appears to be random characters or typing without real words.",
        "improvement": "Take a moment to think, then explain the concept in your own words.",
    },
    "repetition": {
        "headline":    "Your answer mostly repeats the same word.",
        "weakness":    "Repeating a term doesn't show understanding of the concept.",
        "improvement": "Define the term once, then explain how it works and give an example.",
    },
    "too_short": {
        "headline":    "Your answer is too brief.",
        "weakness":    "A few words don't demonstrate technical understanding.",
        "improvement": "Aim for 3-5 sentences. Cover what the concept is, why it matters, and a brief example.",
    },
    "keyword_stuffing": {
        "headline":    "Your answer reads like a list of keywords.",
        "weakness":    "Listing buzzwords without explanation doesn't show understanding.",
        "improvement": "Pick 2-3 core concepts and explain how they connect with a real example.",
    },
    "question_parroting": {
        "headline":    "Your answer mostly repeats the question.",
        "weakness":    "Restating the question doesn't demonstrate that you know the answer.",
        "improvement": "In your own words, explain the concept the question is asking about. Add a concrete example.",
    },
    "low_density": {
        "headline":    "Your answer is mostly generic words.",
        "weakness":    "Filler vocabulary like 'important' or 'really good' doesn't carry technical content.",
        "improvement": "Replace generic adjectives with specific terms, examples, or trade-offs from the topic.",
    },
    "off_topic": {
        "headline":    "Your answer doesn't seem to address the question.",
        "weakness":    "The content doesn't overlap with what the question is asking about.",
        "improvement": "Re-read the question and focus your answer on its specific topic.",
    },
    "truncated_fragment": {
        "headline":    "Your answer stops mid-sentence.",
        "weakness":    "The explanation ends before the point is made, so the key idea is missing.",
        "improvement": "Finish the thought: state the concept, how it works, and one example.",
    },
    "entity_swap": {
        "headline":    "Your answer mixes up the two things being compared.",
        "weakness":    "Properties of one side are attributed to the other, so the comparison is reversed.",
        "improvement": "For each side, state its defining properties in its own sentence, then contrast them.",
    },
}


def generate_feedback(
    answer=None,
    answer_text=None,
    question=None,
    ideal_answer=None,
    skill=None,
    sub_domain=None,
    nlp_score=None,
    svm_label=None,
    kg_score=None,
    final_score=None,
    ner_entities=None,
    guard_reason=None,
):
    # Guard short-circuit — when an anti-gaming rule fired, the round-quality
    # rules below would only mask the real failure mode. Return a payload
    # that names the failure and gives an actionable improvement step.
    if guard_reason and guard_reason in _GUARD_FEEDBACK:
        msg = _GUARD_FEEDBACK[guard_reason]
        return {
            "content":          [msg["headline"]],
            "strengths":        [],
            "weakness":         [msg["weakness"]],
            "next_step":        msg["improvement"],
            "guard_triggered":  guard_reason,
        }

    text = answer_text or answer or ""
    word_count = len(text.split())

    content = []
    strengths = []
    weakness = []
    next_step = ""

    # Rule 1: Length evaluation
    if word_count < 20:
        content.append("Your response was very brief. Technical answers usually require more elaboration.")
        next_step = "Try expanding on the 'why' and 'how' behind your answer."
    elif word_count > 150:
        content.append("You provided a highly detailed explanation.")
        strengths.append("Comprehensive")
        next_step = "Ensure you don't lose the main point in the details. Keep it concise."
    else:
        content.append("Good length and pacing.")
        strengths.append("Concise")

    # Rule 2: Keyword Evaluation
    if ner_entities and len(ner_entities) > 2:
        content.append(f"You successfully included key technical entities like: {', '.join(ner_entities[:3])}.")
        strengths.append("Technical Vocabulary")
    elif ner_entities:
        content.append("You mentioned some core concepts, but there is room for deeper technical vocabulary.")
    else:
        content.append("Your answer lacked specific technical keywords associated with this topic.")
        next_step = "Try incorporating precise industry terminology."

    # Rule 3: Overall Performance
    if svm_label == "Good":
        strengths.append("High Relevance")
        if not next_step:
            next_step = "Maintain this level of detail for future questions."
    elif svm_label == "Poor":
        next_step = "Review the core concepts for this topic before the real interview."

    if not next_step:
        next_step = "Continue to the next round."

    return {
        "content": content,
        "strengths": strengths,
        "weakness": weakness,
        "next_step": next_step,
    }
