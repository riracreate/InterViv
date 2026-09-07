/**
 * Maps /dashboard/:sessionId API payloads into session-dashboard view models.
 * Pure functions — no React — so node:test can cover them without a DOM.
 */

function clamp01(n) {
  return Math.min(1, Math.max(0, n));
}

export function scoreAccent(score) {
  const t = clamp01(Number(score) / 100);
  if (t >= 0.85) return { ring: "from-cyan-400/70 to-blue-500/70", text: "text-cyan-200" };
  if (t >= 0.7) return { ring: "from-sky-400/70 to-cyan-500/70", text: "text-sky-200" };
  if (t >= 0.55) return { ring: "from-blue-400/70 to-indigo-500/70", text: "text-blue-200" };
  return { ring: "from-fuchsia-400/60 to-indigo-500/60", text: "text-fuchsia-200" };
}

function wordCount(text) {
  const t = String(text || "").trim();
  if (!t) return 0;
  return t.split(/\s+/).length;
}

function capitalizeDifficulty(raw) {
  const d = String(raw || "medium").toLowerCase();
  return d.charAt(0).toUpperCase() + d.slice(1);
}

/**
 * Build props for ReviewSummary from the same session object the dashboard fetches.
 * Uses only fields already present on the API / mapped rounds — no invented scores.
 */
export function buildReviewSummaryProps(session, mapped) {
  const rounds = session?.rounds || [];
  const completed = rounds.filter((r) => r.final_score != null);
  const scores = completed.map((r) => Number(r.final_score));
  const overallScore = mapped?.overall?.score ?? Math.round(session?.averages?.final_score || 0);
  const gradeLabel = mapped?.overall?.gradeLabel
    || (overallScore >= 75 ? "Excellent" : overallScore >= 55 ? "Good" : overallScore >= 35 ? "Average" : "Needs Work");

  const guardCount = completed.filter(
    (r) => Boolean(r.guard_applied) || Boolean(r.scoring_breakdown?.guard_applied),
  ).length;

  const avgWords = completed.length
    ? Math.round(completed.reduce((sum, r) => sum + wordCount(r.answer_text), 0) / completed.length)
    : 0;

  const scoreRange = scores.length ? Math.max(...scores) - Math.min(...scores) : 0;

  const topicScores = session?.topic_scores || {};
  let prioritySkills = Object.entries(topicScores).map(([skill, score]) => ({
    skill,
    score: Number(score),
    attempts: completed.filter(
      (r) => (r.skill || r.skill_text || r.question_context?.skill || "") === skill,
    ).length || 1,
  }));

  if (prioritySkills.length === 0) {
    const skills = session?.skills || (session?.skill ? [session.skill] : []);
    prioritySkills = skills.map((skill) => ({
      skill,
      score: overallScore,
      attempts: completed.length || 1,
    }));
  }

  prioritySkills = [...prioritySkills].sort((a, b) => a.score - b.score);

  const mappedRounds = mapped?.rounds || [];
  const priorityRound = [...mappedRounds]
    .filter((r) => typeof r.score === "number")
    .sort((a, b) => a.score - b.score)[0] || null;

  const totalRounds = Number(session?.total_rounds) || rounds.length || completed.length;

  return {
    overallScore,
    gradeLabel,
    completedRounds: completed.length,
    totalRounds,
    guardCount,
    averageWords: avgWords,
    scoreRange,
    prioritySkills,
    priorityRound: priorityRound
      ? {
          id: String(priorityRound.id),
          question: priorityRound.question,
          score: priorityRound.score,
        }
      : null,
    nextStep: session?.next_step || "Continue practising with harder questions to improve your Elo.",
  };
}

export function mapRealDataToDashboard(session) {
  const rounds = session.rounds || [];
  const completed = rounds.filter((r) => r.final_score != null);
  const avg = session.averages?.final_score || 0;
  const skills = session.skills || [session.skill || "General"];
  const elos = session.elo_progression || [];
  const finalElo = elos.length ? elos[elos.length - 1] : (session.elo_after || 1200);
  const topicScores = session.topic_scores || {};

  const gradeLabel = avg >= 75 ? "Excellent" : avg >= 55 ? "Good" : avg >= 35 ? "Average" : "Needs Work";

  const layers = [
    { label: "Layer 1", subtitle: "Content & Relevance", score: session.averages?.nlp_score ?? avg },
    { label: "Layer 2", subtitle: "Quality & Depth", score: session.averages?.kg_score ?? avg * 0.9 },
    { label: "Layer 3", subtitle: "Classifier Signal", score: avg * 0.95 },
  ];

  const radarSkills = Object.keys(topicScores).length > 0
    ? Object.entries(topicScores).map(([skill, value]) => ({ skill, value }))
    : skills.map((s) => ({ skill: s, value: avg }));

  if (radarSkills.length < 3) {
    const extras = [
      { skill: "Clarity", value: avg * 0.9 },
      { skill: "Structure", value: avg * 0.85 },
      { skill: "Depth", value: avg },
    ];
    while (radarSkills.length < 3) radarSkills.push(extras[radarSkills.length]);
  }

  const diffProgression = (session.difficulty_progression || []).map((d, i) => ({
    t: `R${i + 1}`,
    value: d === "hard" ? 60 : d === "medium" ? 35 : 15,
  }));
  const scoreProgression = completed.map((r, i) => ({ t: `R${i + 1}`, value: r.final_score }));

  const roundsForTimeline = completed.map((r, i) => ({
    id: String(i + 1),
    question: r.question || r.question_context?.question || `Round ${i + 1}`,
    idealAnswer: r.ideal_answer || r.question_context?.ideal_answer || "",
    answer: r.answer_text || "",
    score: r.final_score,
    confidenceBand: typeof r.confidence_band === "number" ? r.confidence_band : null,
    difficulty: capitalizeDifficulty(r.difficulty),
    feedback: r.feedback?.next_step || r.feedback?.content?.[0] || "",
    topic: r.topic || r.sub_domain || r.question_context?.topic || r.question_context?.sub_domain || "",
    questionType: r.question_type || r.question_context?.question_type || "",
    followups: r.followups || r.question_context?.followups || [],
    scoring_breakdown: r.scoring_breakdown || null,
    scoring_mode: r.scoring_mode || "unknown",
    scoring_mode_label: r.scoring_mode_label || null,
    evidence_kind: r.evidence_kind || null,
  }));

  const strengths = [];
  const weaknesses = [];
  if (session.breakdown) {
    const { Good = 0, Average = 0, Poor = 0 } = session.breakdown;
    if (Good > 0) {
      strengths.push({
        title: `${Good} Strong Round${Good > 1 ? "s" : ""}`,
        detail: "You achieved Good-band scores on these rounds — keep up this depth.",
      });
    }
    if (Average > 0) {
      weaknesses.push({
        title: `${Average} Average Round${Average > 1 ? "s" : ""}`,
        detail: "These rounds have room for more detail and concrete examples.",
      });
    }
    if (Poor > 0) {
      weaknesses.push({
        title: `${Poor} Round${Poor > 1 ? "s" : ""} to Revisit`,
        detail: "Consider reviewing these topics before your next session.",
      });
    }
  }
  if (strengths.length === 0) {
    strengths.push({ title: "Participation", detail: "You completed all rounds — consistency is key." });
  }
  if (weaknesses.length === 0) {
    weaknesses.push({
      title: "Push for depth",
      detail: "Try to include trade-offs, examples, and edge cases in each answer.",
    });
  }

  const nextStepText = session.next_step || "Continue practising with harder questions to improve your Elo.";
  const feedbackCards = [
    {
      id: "c1",
      title: "C4 — Context",
      tag: "Structure",
      body: `Your overall session score was ${Math.round(avg)}%. ${nextStepText}`,
    },
    {
      id: "c2",
      title: "C4 — Containers",
      tag: "Clarity",
      body: `Difficulty adapted across ${completed.length} rounds. Final Elo: ${finalElo}.`,
    },
    {
      id: "c3",
      title: "C4 — Components",
      tag: "Signal",
      body: `Skills tested: ${skills.join(", ")}.`,
    },
    {
      id: "c4",
      title: "C4 — Code",
      tag: "Delivery",
      body: `Your best round scored ${Math.round(Math.max(...completed.map((r) => r.final_score ?? 0), 0))}%. Aim to replicate that depth.`,
    },
  ];

  const mapped = {
    session: {
      title: "Adaptive Mock Interview",
      role: skills.join(" + "),
      dateLabel: new Date(session.started_at || Date.now()).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      }),
      durationLabel: `${completed.length} rounds`,
      skillFocus: skills[0] || "General",
    },
    overall: { score: Math.round(avg), gradeLabel, deltaLabel: `${Math.round(avg)}% avg score` },
    layers,
    radar: radarSkills,
    performance: { finalRating: finalElo, difficulty: diffProgression, score: scoreProgression },
    rounds: roundsForTimeline,
    highlights: { strengths, weaknesses },
    feedbackCards,
  };

  mapped.reviewSummary = buildReviewSummaryProps(session, mapped);
  return mapped;
}
