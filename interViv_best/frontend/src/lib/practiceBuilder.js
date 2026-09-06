/**
 * Practice Hub — map UI form state to POST /session/start bodies.
 * Pure helpers for tests + Practice page.
 */

export const PRACTICE_MODES = [
  { id: 'full', title: 'Full interview', blurb: 'Multi-skill free-text interview with existing voice input.' },
  { id: 'oa_sql', title: 'OA + SQL', blurb: 'MCQ assessment followed by SQL problems (not a general coding judge).' },
  { id: 'problems', title: 'Problem practice', blurb: 'Browse existing MCQ and SQL bank items.' },
  { id: 'custom', title: 'Custom interview builder', blurb: 'Choose time, count, and a real round mix.' },
];

export const REAL_ROUND_TYPES = ['technical_short_answer', 'mcq', 'sql'];

/**
 * @param {object} form
 * @returns {{ error?: string, payload?: object }}
 */
export function mapCustomBuilderToStartPayload(form) {
  const skills = (form.skills || []).map((s) => String(s).trim()).filter(Boolean);
  if (skills.length === 0) {
    return { error: 'Select at least one skill.' };
  }

  const totalMinutes = Number(form.totalMinutes);
  const questionCount = Number(form.questionCount);
  if (!Number.isFinite(totalMinutes) || totalMinutes < 5 || totalMinutes > 180) {
    return { error: 'Total time must be between 5 and 180 minutes.' };
  }
  if (!Number.isFinite(questionCount) || questionCount < 1 || questionCount > 20) {
    return { error: 'Number of questions must be between 1 and 20.' };
  }

  const includeTechnical = Boolean(form.includeTechnical);
  const includeMcq = Boolean(form.includeMcq);
  const includeSql = Boolean(form.includeSql);
  if (!includeTechnical && !includeMcq && !includeSql) {
    return { error: 'Select at least one round type (free-text, MCQ, or SQL).' };
  }

  // Session API has no text/voice mode field — voice stays on the interview page.
  if (form.mode && form.mode !== 'text') {
    return {
      error:
        'Voice/mixed mode is not a separate session type. Use text start; voice input is already on the interview page.',
    };
  }

  const blocks = [];
  if (includeMcq) blocks.push('mcq');
  if (includeSql) blocks.push('sql');
  const blockCount = blocks.length;
  let technicalCount = 0;
  if (includeTechnical) {
    technicalCount = Math.max(1, questionCount - blockCount);
  } else if (questionCount !== blockCount) {
    return {
      error:
        `Without free-text rounds, question count must equal selected MCQ/SQL blocks (${blockCount}).`,
    };
  }

  let round_plan = [
    ...Array.from({ length: technicalCount }, () => 'technical_short_answer'),
    ...blocks,
  ];

  const mcqCount = includeMcq
    ? Math.max(1, Number(form.mcqCount) || Math.min(10, Math.max(3, questionCount)))
    : undefined;
  const sqlCount = includeSql ? Math.max(1, Number(form.sqlCount) || 1) : 1;

  // Expand SQL into multiple plan entries when requested.
  if (includeSql && sqlCount > 1) {
    const withoutSql = round_plan.filter((t) => t !== 'sql');
    round_plan = [...withoutSql, ...Array.from({ length: sqlCount }, () => 'sql')];
  }

  const payload = {
    skills,
    rounds_per_skill: 1,
    round_plan,
    round_type: round_plan[0],
    round_config: {
      duration_minutes: totalMinutes,
      ...(includeMcq ? { count: mcqCount } : {}),
      ...(includeSql && form.problemId ? { problem_id: form.problemId } : {}),
    },
    target_company_id: form.targetCompanyId || null,
    target_role_id: form.targetRoleId || null,
  };
  if (form.candidateId) payload.candidate_id = form.candidateId;

  return { payload };
}

/**
 * OA + SQL combined mode → start body.
 */
export function mapOaSqlToStartPayload(form) {
  const skills = (form.skills || []).map((s) => String(s).trim()).filter(Boolean);
  if (skills.length === 0) return { error: 'Select at least one skill.' };

  const duration = Number(form.durationMinutes) || 45;
  const mcqCount = Number(form.mcqCount) || 10;
  const sqlCases = Number(form.sqlCases) || 1;
  if (mcqCount < 1 || mcqCount > 30) return { error: 'MCQ count must be 1–30.' };
  if (sqlCases < 1 || sqlCases > 5) return { error: 'SQL cases must be 1–5.' };

  const round_plan = ['mcq', ...Array.from({ length: sqlCases }, () => 'sql')];
  const payload = {
    skills,
    rounds_per_skill: 1,
    round_plan,
    round_type: 'mcq',
    round_config: {
      duration_minutes: duration,
      count: mcqCount,
    },
    target_company_id: form.targetCompanyId || null,
    target_role_id: form.targetRoleId || null,
  };
  if (form.candidateId) payload.candidate_id = form.candidateId;
  return { payload };
}

/**
 * Full interview → existing technical multi-skill start.
 * Difficulty is Elo-driven on the server; no inventing a difficulty field.
 */
export function mapFullInterviewToStartPayload(form) {
  const skills = (form.skills || []).map((s) => String(s).trim()).filter(Boolean);
  if (skills.length === 0) return { error: 'Select at least one skill.' };
  const rounds = Number(form.roundsPerSkill) || 3;
  if (rounds < 1 || rounds > 10) return { error: 'Rounds per skill must be 1–10.' };

  const payload = {
    skills,
    rounds_per_skill: rounds,
    round_type: 'technical_short_answer',
    target_company_id: form.targetCompanyId || null,
    target_role_id: form.targetRoleId || null,
  };
  if (form.candidateId) payload.candidate_id = form.candidateId;
  // Optional timer hint for the interview UI only (not a backend field).
  if (form.timerSeconds) payload._client_timer_seconds = Number(form.timerSeconds);
  return { payload };
}

/**
 * Single bank item → start body.
 */
export function mapProblemItemToStartPayload(item, form = {}) {
  if (!item || !item.id || !item.type) {
    return { error: 'Pick an MCQ or SQL item from the bank.' };
  }
  const skills = (form.skills || [item.skill || 'DBMS']).filter(Boolean);
  if (item.type === 'mcq') {
    return {
      payload: {
        skills,
        rounds_per_skill: 1,
        round_type: 'mcq',
        round_config: {
          count: 1,
          duration_minutes: Number(form.durationMinutes) || 15,
          question_ids: [item.id],
        },
        ...(form.candidateId ? { candidate_id: form.candidateId } : {}),
      },
    };
  }
  if (item.type === 'sql') {
    return {
      payload: {
        skills: skills.length ? skills : ['DBMS'],
        rounds_per_skill: 1,
        round_type: 'sql',
        round_config: {
          duration_minutes: Number(form.durationMinutes) || 25,
          problem_id: item.id,
        },
        ...(form.candidateId ? { candidate_id: form.candidateId } : {}),
      },
    };
  }
  return { error: `Unsupported bank item type "${item.type}".` };
}
