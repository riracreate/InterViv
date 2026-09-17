/**
 * Maps /dashboard/:sessionId API payloads into session-dashboard view models.
 * Pure functions — no React — so node:test can cover them without a DOM.
 */
import { unscoredReasonLabel } from "./accountOverview.js";
import { formatMcqAnswerSummary, mapMcqReview } from "./mcqReviewMapping.js";

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

// The API sends a null average when no measured round was scored (e.g. an
// expired round that could not be evaluated). Absence is not a zero.
function measuredAverage(session) {
  const avg = session?.averages?.final_score;
  return typeof avg === "number" && Number.isFinite(avg) ? avg : null;
}

function gradeFor(score) {
  if (score == null) return "Not measured";
  return score >= 75 ? "Excellent" : score >= 55 ? "Good" : score >= 35 ? "Average" : "Needs Work";
}

// Rounds the API reports as unscored (coverage.unscored_rounds, the same
// list Progress renders), labeled with Progress's wording.
function unscoredRounds(session) {
  return (session?.coverage?.unscored_rounds || []).map((u) => ({
    round: u.round,
    label: unscoredReasonLabel(u),
  }));
}

const BLOCK_CATEGORY_LABELS = {
  verbal: "Verbal",
  oa: "OA",
  sql: "SQL",
  coding: "Coding",
  system_design: "System design",
  ml_primitives: "ML primitives",
  interview: "Interview",
};

// Each block's own metric. Never blended across blocks: MCQ accuracy,
// SQL correctness, interview scores, and self-ratings stay separate.
export function blockMetricLabel(block) {
  const category = String(block?.block_category || "").toLowerCase();
  const types = block?.round_types || [];
  if (category === "verbal" || category === "oa" || types.includes("mcq")) {
    return "MCQ accuracy";
  }
  if (category === "sql" || types.includes("sql")) return "SQL correctness";
  if (category === "coding" || types.includes("coding")) return "Coding score";
  if (category === "system_design" || types.includes("system_design")) {
    return "Self-reported score";
  }
  if (category === "ml_primitives" || types.includes("ml_primitives")) {
    return "Ungraded practice";
  }
  return "Interview score";
}

export function blockDisplayLabel(block, index) {
  const category = String(block?.block_category || "").toLowerCase();
  const name = BLOCK_CATEGORY_LABELS[category] || "Practice";
  const position = block?.block_position ?? index + 1;
  return `Block ${position} · ${name}`;
}

// Multi-block sessions only (block_plan length > 1). Legacy sessions
// without a block plan keep their historical single-overall rendering.
export function isMultiBlockSession(session) {
  return Array.isArray(session?.block_plan) && session.block_plan.length > 1;
}

function mapBlocks(session) {
  const results = session?.block_results || [];
  return results.map((b, index) => {
    const average = typeof b?.average_score === "number" && Number.isFinite(b.average_score)
      ? b.average_score
      : null;
    const selfAverage = typeof b?.self_reported_average === "number" && Number.isFinite(b.self_reported_average)
      ? b.self_reported_average
      : null;
    return {
      position: b?.block_position ?? index + 1,
      title: blockDisplayLabel(b, index),
      metric: blockMetricLabel(b),
      average,
      selfReportedAverage: selfAverage,
      skills: b?.skills || [],
      rounds: Number(b?.rounds) || 0,
      attempted: Number(b?.attempted_rounds ?? b?.scored_rounds) || 0,
      scored: Number(b?.scored_rounds) || 0,
      unscored: Number(b?.unscored_rounds ?? 0) || 0,
      scoringModes: b?.scoring_modes || [],
      suggestion: b?.suggestion?.text || null,
    };
  });
}

// True when the server average blends measured rounds from more than one
// block. Single-block and legacy sessions are never blended.
function isBlendedSession(session) {
  if (!isMultiBlockSession(session)) return false;
  const measuredBlocks = (session?.block_results || []).filter(
    (b) => Number(b?.measured_rounds) > 0
  );
  return measuredBlocks.length > 1;
}

/**
 * Build props for ReviewSummary from the same session object the dashboard fetches.
 * Uses only fields already present on the API / mapped rounds — no invented scores.
 */
export function buildReviewSummaryProps(session, mapped) {
  const rounds = session?.rounds || [];
  const completed = rounds.filter((r) => r.final_score != null);
  const scores = completed.map((r) => Number(r.final_score));
  const average = measuredAverage(session);
  const overallScore = mapped ? mapped.overall.score : average == null ? null : Math.round(average);
  const gradeLabel = mapped?.overall?.gradeLabel || gradeFor(overallScore);

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

  if (prioritySkills.length === 0 && overallScore != null) {
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
    blended: mapped?.blended === true,
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
    unscored: unscoredRounds(session),
    nextStep: session?.next_step || "Continue practising with harder questions to improve your Elo.",
  };
}

export function mapRealDataToDashboard(session) {
  const rounds = session.rounds || [];
  const completed = rounds.filter((r) => r.final_score != null);
  const average = measuredAverage(session);
  const measured = average != null;
  const avg = average ?? 0; // only read below when measured
  const unscored = unscoredRounds(session);
  const skills = session.skills || [session.skill || "General"];
  const elos = session.elo_progression || [];
  const finalElo = elos.length ? elos[elos.length - 1] : (session.elo_after || 1200);
  const topicScores = session.topic_scores || {};
  const blocks = mapBlocks(session);
  // A blended average mixes measured rounds from several blocks (e.g.
  // MCQ accuracy with interview scores). It is never shown as one
  // unexplained percentage; per-block cards carry the metrics instead.
  const blended = isBlendedSession(session);

  const gradeLabel = blended ? "Mixed session" : gradeFor(average);

  const layers = measured && !blended ? [
    { label: "Layer 1", subtitle: "Content & Relevance", score: session.averages?.nlp_score ?? avg },
    { label: "Layer 2", subtitle: "Quality & Depth", score: session.averages?.kg_score ?? avg * 0.9 },
    { label: "Layer 3", subtitle: "Classifier Signal", score: avg * 0.95 },
  ] : [];

  const radarSkills = !measured || blended ? [] : Object.keys(topicScores).length > 0
    ? Object.entries(topicScores).map(([skill, value]) => ({ skill, value }))
    : skills.map((s) => ({ skill: s, value: avg }));

  if (measured && !blended && radarSkills.length < 3) {
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

  const roundsForTimeline = completed.map((r, i) => {
    const roundType = r.round_type || r.question_context?.round_type || "";
    const assessmentCompleted = String(session?.status || "").toLowerCase() === "completed";
    const mcqReview = roundType === "mcq"
      ? mapMcqReview(r, { assessmentCompleted })
      : null;
    let answer = r.answer_text || "";
    if (roundType === "mcq" && mcqReview) {
      answer = formatMcqAnswerSummary(mcqReview) || answer;
    } else if (roundType === "sql" && r.artifact_json) {
      const art = r.artifact_json;
      const passed = art.cases_passed;
      const total = art.evaluation_cases;
      if (passed != null && total != null) {
        answer = `SQL submitted · ${passed}/${total} cases passed`;
      }
    }
    return {
      id: String(i + 1),
      roundType,
      question: r.question || r.question_context?.question || `Round ${i + 1}`,
      idealAnswer: roundType === "mcq"
        ? ""
        : (r.ideal_answer || r.question_context?.ideal_answer || ""),
      answer,
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
      mcqReview,
      reviewPolicy: r.review_policy || r.config_json?.review_policy || null,
      feedbackSource: r.feedback_source || r.narration_source || null,
      scorerProvenance: r.scorer_provenance || r.attempt_snapshot?.scorer_provenance || null,
    };
  });

  const mcqReviews = roundsForTimeline
    .map((r) => r.mcqReview)
    .filter(Boolean);

  const strengths = [];
  const weaknesses = [];
  if (measured && session.breakdown) {
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
  // Completion is never claimed for a round that could not be evaluated.
  if (measured && strengths.length === 0 && unscored.length === 0) {
    strengths.push({ title: "Participation", detail: "You completed all rounds — consistency is key." });
  }
  if (measured && weaknesses.length === 0) {
    weaknesses.push({
      title: "Push for depth",
      detail: "Try to include trade-offs, examples, and edge cases in each answer.",
    });
  }

  const nextStepText = session.next_step || "Continue practising with harder questions to improve your Elo.";
  const measuredBlockCount = (session?.block_results || []).filter(
    (b) => Number(b?.measured_rounds) > 0
  ).length;
  const feedbackCards = [
    {
      id: "c1",
      title: "C4 — Context",
      tag: "Structure",
      body: blended
        ? `This session combined ${measuredBlockCount} measured blocks with different metrics. See per-block results below — scores are not blended into one percentage. ${nextStepText}`
        : measured
          ? `Your overall session score was ${Math.round(avg)}%. ${nextStepText}`
          : `No round in this session produced a score. ${unscored.length} unscored round${unscored.length === 1 ? " is" : "s are"} excluded from every average.`,
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
      body: completed.length
        ? `Your best round scored ${Math.round(Math.max(...completed.map((r) => r.final_score ?? 0), 0))}%. Aim to replicate that depth.`
        : "No scored rounds in this session.",
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
    overall: blended
      ? { score: null, gradeLabel, deltaLabel: "See per-block results below" }
      : measured
        ? { score: Math.round(avg), gradeLabel, deltaLabel: `${Math.round(avg)}% avg score` }
        : { score: null, gradeLabel, deltaLabel: "No scored rounds" },
    blended,
    multiBlock: isMultiBlockSession(session),
    blocks,
    layers,
    radar: radarSkills,
    performance: { finalRating: finalElo, difficulty: diffProgression, score: scoreProgression },
    rounds: roundsForTimeline,
    mcqReviews,
    highlights: { strengths, weaknesses },
    feedbackCards,
  };

  mapped.reviewSummary = buildReviewSummaryProps(session, mapped);
  return mapped;
}
