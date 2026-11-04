/**
 * Practice Hub — map UI form state to POST /session/start bodies.
 * Pure helpers for tests + Practice page.
 */

export const PRACTICE_MODES = [
  { id: 'full', title: 'Full interview', blurb: 'Multi-skill free-text interview with existing voice input.' },
  { id: 'oa_sql', title: 'OA + SQL', blurb: 'MCQ assessment followed by SQL problems (not a general coding judge).' },
  { id: 'problems', title: 'Problem practice', blurb: 'Browse existing MCQ, SQL, and coding bank items.' },
  { id: 'custom', title: 'Custom interview builder', blurb: 'Choose time, count, and a real round mix.' },
];

export const REAL_ROUND_TYPES = ['technical_short_answer', 'mcq', 'sql', 'coding', 'system_design', 'ml_primitives'];

export const PRESET_VERSION = 1;
export const BUILDER_DRAFT_VERSION = 1;
export const VERBAL_SKILL = 'Verbal Ability';
export const SYSTEM_DESIGN_SKILL = 'System Design';

// Browser copy of the builder draft, one key per account (Phase AB). The
// unnamespaced key predates this, may hold another account's draft, and is
// never read; api.js removes it whenever the signed-in account changes.
export const LEGACY_BUILDER_DRAFT_KEY = 'interviv-builder-draft-v1';

export function builderDraftKey(userId) {
  return userId ? `${LEGACY_BUILDER_DRAFT_KEY}:${userId}` : null;
}

export function loadLocalBuilderDraft(userId) {
  try {
    const key = builderDraftKey(userId);
    const local = key && JSON.parse(localStorage.getItem(key) || 'null');
    return local && !validateDraftPayload(local) && local.blocks?.length ? local.blocks : null;
  } catch {
    return null;
  }
}

export function saveLocalBuilderDraft(userId, blocks) {
  const key = builderDraftKey(userId);
  if (!key) return;
  try {
    localStorage.setItem(key, JSON.stringify({ version: BUILDER_DRAFT_VERSION, blocks }));
  } catch { /* storage full or unavailable */ }
}

// Phase B standalone entries: one clear start per available block.
// Phase C adds coding practice backed by the execution service.
export const STANDALONE_MODES = [
  { id: 'verbal', title: 'Verbal Ability', blurb: 'English MCQs: grammar, vocabulary, comprehension, ordering, idioms.' },
  { id: 'oa', title: 'OA practice', blurb: 'Technical MCQs restricted to your selected topics.' },
  { id: 'sql', title: 'SQL practice', blurb: 'SQL problems with schemas and execution-based evaluation.' },
  { id: 'coding', title: 'Coding practice', blurb: 'Python problems with visible examples and hidden-test scoring.' },
  { id: 'system_design', title: 'System design', blurb: 'Written design notes get a practice estimate per criterion; self-assessment ratings are optional (no auto diagram scoring).' },
  { id: 'ml_primitives', title: 'ML primitives', blurb: 'Implement numerical algorithms with NumPy. Graded when the local runner is on; otherwise submissions are stored ungraded.' },
  { id: 'interview', title: 'Interview practice', blurb: 'Technical/HR questions with text and voice input.' },
];

/**
 * Practice home groups every mode into four tracks (overhaul Phase 6).
 * Verbal Ability is an English MCQ section, so it sits with OA & SQL.
 */
export const PRACTICE_TRACKS = [
  { id: 'mock', title: 'AI mock interview', blurb: 'Spoken or typed interview questions with rubric feedback.', modes: ['interview', 'full'] },
  { id: 'coding_ml', title: 'Coding & ML', blurb: 'Solve problems against visible and hidden tests.', modes: ['coding', 'problems', 'ml_primitives'] },
  { id: 'oa_sql', title: 'OA & SQL', blurb: 'Timed MCQs and SQL queries, as in online assessments.', modes: ['oa', 'verbal', 'sql', 'oa_sql'] },
  { id: 'design_custom', title: 'System design & custom', blurb: 'Design prompts, or build your own round mix.', modes: ['system_design', 'custom'] },
];

export function modeById(id) {
  return [...STANDALONE_MODES, ...PRACTICE_MODES].find((m) => m.id === id) || null;
}

export const BLOCK_CATEGORIES = ['verbal', 'oa', 'sql', 'coding', 'system_design', 'ml_primitives', 'interview'];

export function blockCategoryButtonLabel(category) {
  if (category === 'verbal') return 'Verbal';
  if (category === 'oa') return 'OA';
  if (category === 'sql') return 'SQL';
  if (category === 'coding') return 'Coding';
  if (category === 'system_design') return 'System design';
  if (category === 'ml_primitives') return 'ML primitives';
  return 'Interview';
}

export function createBlockId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
  return `block-${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
}

export function blockTemplate(category) {
  if (category === 'verbal') {
    return { round_type: 'mcq', category: 'verbal', skills: [VERBAL_SKILL], count: 15, duration_minutes: 20 };
  }
  if (category === 'oa') {
    return { round_type: 'mcq', category: 'oa', skills: ['DBMS'], count: 10, duration_minutes: 20 };
  }
  if (category === 'sql') {
    return { round_type: 'sql', category: 'sql', skills: ['SQL'], count: 1, duration_minutes: 25 };
  }
  if (category === 'coding') {
    return { round_type: 'coding', category: 'coding', skills: ['DSA'], count: 1, duration_minutes: 30 };
  }
  if (category === 'ml_primitives') {
    return { round_type: 'ml_primitives', category, skills: ['ML primitives'], count: 1, duration_minutes: 30, language: 'python' };
  }
  if (category === 'system_design') {
    return {
      round_type: 'system_design',
      category: 'system_design',
      skills: [SYSTEM_DESIGN_SKILL],
      count: 1,
      duration_minutes: 25,
    };
  }
  return { round_type: 'technical_short_answer', category: 'interview', skills: ['DBMS'], count: 3 };
}

// Adding a block appends; it never erases the existing sequence.
export function addBlock(blocks, category) {
  const next = Array.isArray(blocks) ? [...blocks] : [];
  next.push({ id: createBlockId(), ...blockTemplate(category) });
  return next;
}

export function removeBlock(blocks, id) {
  return (blocks || []).filter((b) => b.id !== id);
}

export function moveBlock(blocks, id, direction) {
  const list = [...(blocks || [])];
  const index = list.findIndex((b) => b.id === id);
  if (index < 0) return list;
  const target = direction === 'up' ? index - 1 : index + 1;
  if (target < 0 || target >= list.length) return list;
  const [item] = list.splice(index, 1);
  list.splice(target, 0, item);
  return list;
}

export function duplicateBlock(blocks, id) {
  const list = [...(blocks || [])];
  const index = list.findIndex((b) => b.id === id);
  if (index < 0) return list;
  const copy = { ...list[index], id: createBlockId() };
  list.splice(index + 1, 0, copy);
  return list;
}

export function formatBlockLabel(block) {
  const category = String(block?.category || '').toLowerCase();
  const count = Number(block?.count) || 1;
  const noun = count === 1 ? 'question' : 'questions';
  if (category === 'verbal') return `Verbal · ${count} ${noun}`;
  if (category === 'oa') return `OA · ${count} ${noun}`;
  if (category === 'sql') return `SQL · ${count} ${count === 1 ? 'problem' : 'problems'}`;
  if (category === 'ml_primitives') return `ML primitives · ${count} ${count === 1 ? 'problem' : 'problems'} (ungraded)`;
  if (category === 'coding') return `Coding · ${count} ${count === 1 ? 'problem' : 'problems'}`;
  if (category === 'system_design') return `System design · ${count} ${count === 1 ? 'prompt' : 'prompts'}`;
  return `Interview · ${count} ${noun}`;
}

export function totalTimeSummary(blocks) {
  let timed = 0;
  let untimed = 0;
  for (const b of blocks || []) {
    if (Number(b?.duration_minutes) > 0) timed += Number(b.duration_minutes);
    else untimed += 1;
  }
  return { timedMinutes: timed, untimedBlocks: untimed, blockCount: (blocks || []).length };
}

export function validateBuilderBlocks(blocks) {
  if (!Array.isArray(blocks) || blocks.length === 0) return 'Add at least one block.';
  if (blocks.length > 10) return 'At most 10 blocks are allowed.';
  for (let i = 0; i < blocks.length; i += 1) {
    const b = blocks[i] || {};
    const label = `Block ${i + 1}`;
    if (!['mcq', 'sql', 'coding', 'system_design', 'ml_primitives', 'technical_short_answer'].includes(b.round_type)) {
      return `${label}: choose a supported round type.`;
    }
    if (b.category === 'verbal') {
      const skills = (b.skills || []).map((s) => String(s).trim());
      if (skills.length !== 1 || skills[0] !== VERBAL_SKILL) {
        return `${label}: Verbal blocks use Verbal Ability only.`;
      }
      if (b.round_type !== 'mcq') return `${label}: Verbal blocks are MCQ assessments.`;
    }
    if (b.category === 'oa') {
      if ((b.skills || []).length === 0) return `${label}: select at least one topic.`;
      if ((b.skills || []).includes(VERBAL_SKILL)) {
        return `${label}: OA blocks must not include Verbal Ability; add a Verbal block.`;
      }
    }
    if (b.category === 'coding') {
      if (b.round_type !== 'coding') return `${label}: Coding blocks are coding rounds.`;
      if ((b.skills || []).includes(VERBAL_SKILL)) {
        return `${label}: Coding blocks must not include Verbal Ability.`;
      }
    }
    if (b.category === 'ml_primitives' && b.round_type !== 'ml_primitives') {
      return `${label}: ML primitive blocks use ml_primitives rounds.`;
    }
    if (b.category === 'system_design') {
      if (b.round_type !== 'system_design') {
        return `${label}: System-design blocks use system_design rounds.`;
      }
    }
    if (b.category === 'interview' && (b.skills || []).length === 0) {
      return `${label}: select at least one skill.`;
    }
    if (b.topic != null && b.topic !== '') {
      if (b.category !== 'interview') {
        return `${label}: topic is only supported for interview blocks.`;
      }
      if (typeof b.topic !== 'string' || !b.topic.trim() || b.topic.trim().length > 120) {
        return `${label}: topic must be 1–120 characters.`;
      }
    }
    const count = Number(b.count);
    if (!Number.isFinite(count) || count < 1) return `${label}: count must be at least 1.`;
    if ((b.category === 'oa' || b.category === 'verbal') && count > 30) {
      return `${label}: MCQ count must be 1–30.`;
    }
    if (b.category === 'sql' && count > 5) return `${label}: SQL count must be 1–5.`;
    if (b.category === 'ml_primitives' && count > 5) return `${label}: ML primitive count must be 1–5.`;
    if (b.category === 'coding' && count > 5) return `${label}: Coding count must be 1–5.`;
    if (b.category === 'system_design' && count > 5) {
      return `${label}: System-design count must be 1–5.`;
    }
    if (b.category === 'interview' && count > 10) return `${label}: interview count must be 1–10.`;
    if (b.duration_minutes != null) {
      const minutes = Number(b.duration_minutes);
      if (!Number.isFinite(minutes) || minutes < 1 || minutes > 180) {
        return `${label}: time budget must be 1–180 minutes.`;
      }
    }
    if (b.difficulty != null && b.difficulty !== '' && !['easy', 'medium', 'hard'].includes(String(b.difficulty).toLowerCase())) {
      return `${label}: difficulty must be easy, medium, or hard.`;
    }
  }
  return null;
}

export function mapBlocksToStartPayload(blocks, form = {}) {
  const error = validateBuilderBlocks(blocks);
  if (error) return { error };
  const payload = {
    blocks: (blocks || []).map((b) => {
      const item = {
        round_type: b.round_type,
        category: b.category,
        skills: (b.skills || []).map((s) => String(s).trim()).filter(Boolean),
        count: Number(b.count),
      };
      if (b.id) item.id = b.id;
      if (b.duration_minutes != null) item.duration_minutes = Number(b.duration_minutes);
      if (b.difficulty) item.difficulty = String(b.difficulty).toLowerCase();
      // Unrestricted topics are omitted, never sent as "general".
      if (typeof b.topic === 'string' && b.topic.trim()) item.topic = b.topic.trim();
      if (b.question_ids?.length) item.question_ids = [...b.question_ids];
      if (b.problem_ids?.length) item.problem_ids = [...b.problem_ids];
      if (b.language) item.language = b.language;
      if (b.category === 'interview' && b.allow_optional_follow_ups) {
        item.allow_optional_follow_ups = true;
      }
      if (b.review_policy) item.review_policy = b.review_policy;
      return item;
    }),
    target_company_id: form.targetCompanyId || null,
    target_role_id: form.targetRoleId || null,
  };
  if (form.candidateId) payload.candidate_id = form.candidateId;
  if (form.practiceMode === 'assessment' || form.practiceMode === 'coached_practice') {
    payload.practice_mode = form.practiceMode;
  }
  if (typeof form.allowOptionalFollowUps === 'boolean') {
    payload.allow_optional_follow_ups = form.allowOptionalFollowUps;
  }
  return { payload };
}

export function mapStandaloneToStartPayload(kind, form = {}) {
  const template = blockTemplate(kind);
  if (kind === 'verbal') {
    const count = Number(form.count) || 15;
    if (count < 1 || count > 30) return { error: 'Verbal count must be 1–30.' };
    const duration = Number(form.durationMinutes) || 20;
    if (duration < 1 || duration > 180) return { error: 'Time budget must be 1–180 minutes.' };
    return mapBlocksToStartPayload(
      [{ ...template, count, duration_minutes: duration }],
      form,
    );
  }
  if (kind === 'oa') {
    const skills = (form.skills || []).map((s) => String(s).trim()).filter(Boolean);
    if (skills.length === 0) return { error: 'Select at least one topic.' };
    if (skills.includes(VERBAL_SKILL)) {
      return { error: 'OA topics must not include Verbal Ability; use Verbal practice.' };
    }
    const count = Number(form.count) || 10;
    if (count < 1 || count > 30) return { error: 'OA count must be 1–30.' };
    const duration = Number(form.durationMinutes) || 20;
    if (duration < 1 || duration > 180) return { error: 'Time budget must be 1–180 minutes.' };
    return mapBlocksToStartPayload(
      [{ ...template, skills, count, duration_minutes: duration, difficulty: form.difficulty || undefined }],
      form,
    );
  }
  if (kind === 'sql') {
    const duration = Number(form.durationMinutes) || 25;
    if (duration < 1 || duration > 180) return { error: 'Time budget must be 1–180 minutes.' };
    const block = { ...template, duration_minutes: duration };
    if (form.problemId) block.problem_ids = [form.problemId];
    else block.count = 1;
    if (form.difficulty) block.difficulty = String(form.difficulty).toLowerCase();
    return mapBlocksToStartPayload([block], form);
  }
  if (kind === 'coding' || kind === 'ml_primitives') {
    const duration = Number(form.durationMinutes) || 30;
    if (duration < 1 || duration > 180) return { error: 'Time budget must be 1–180 minutes.' };
    const block = { ...template, duration_minutes: duration };
    if (form.problemId) block.problem_ids = [form.problemId];
    else block.count = 1;
    if (form.difficulty) block.difficulty = String(form.difficulty).toLowerCase();
    return mapBlocksToStartPayload([block], form);
  }
  if (kind === 'system_design') {
    const duration = Number(form.durationMinutes) || 25;
    if (duration < 1 || duration > 180) return { error: 'Time budget must be 1–180 minutes.' };
    const count = Number(form.count) || 1;
    if (count < 1 || count > 5) return { error: 'System-design count must be 1–5.' };
    const block = { ...template, count, duration_minutes: duration };
    if (form.problemId) block.problem_ids = [form.problemId];
    if (form.difficulty) block.difficulty = String(form.difficulty).toLowerCase();
    return mapBlocksToStartPayload([block], form);
  }
  if (kind === 'interview') {
    const skills = (form.skills || []).map((s) => String(s).trim()).filter(Boolean);
    if (skills.length === 0) return { error: 'Select at least one skill.' };
    const count = Number(form.count) || 3;
    if (count < 1 || count > 10) return { error: 'Interview count must be 1–10.' };
    const block = { ...template, skills, count };
    if (form.durationMinutes) block.duration_minutes = Number(form.durationMinutes);
    if (form.difficulty) block.difficulty = String(form.difficulty).toLowerCase();
    if (typeof form.topic === 'string' && form.topic.trim()) block.topic = form.topic.trim();
    return mapBlocksToStartPayload([block], form);
  }
  return { error: `Unsupported standalone practice "${kind}".` };
}

export function validatePresetPayload(preset) {
  if (!preset || typeof preset !== 'object') return 'Preset must be an object.';
  if (Number(preset.version) !== PRESET_VERSION) {
    return `Unsupported preset version ${preset.version}; expected ${PRESET_VERSION}.`;
  }
  if (!preset.name || !String(preset.name).trim()) return 'Preset name is required.';
  return validateBuilderBlocks(preset.blocks);
}

export function validateDraftPayload(draft) {
  if (!draft || typeof draft !== 'object') return 'Draft must be an object.';
  if (Number(draft.version) !== BUILDER_DRAFT_VERSION) {
    return `Unsupported draft version ${draft.version}; expected ${BUILDER_DRAFT_VERSION}.`;
  }
  if (!draft.blocks || draft.blocks.length === 0) return null;
  return validateBuilderBlocks(draft.blocks);
}

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
    return { error: 'Pick an MCQ, SQL, or coding item from the bank.' };
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
  if (item.type === 'coding') {
    return {
      payload: {
        skills: skills.length ? skills : ['DSA'],
        rounds_per_skill: 1,
        round_type: 'coding',
        round_config: {
          duration_minutes: Number(form.durationMinutes) || 30,
          problem_id: item.id,
        },
        ...(form.candidateId ? { candidate_id: form.candidateId } : {}),
      },
    };
  }
  return { error: `Unsupported bank item type "${item.type}".` };
}

/**
 * Required skill names for a role from GET /companies. The API sends
 * ``skill_requirements: [{skill, display_name, ...}]``; older shapes are
 * still accepted. Pure for tests.
 */
export function roleRequiredSkills(role) {
  const list = role?.skill_requirements || role?.required_skills || role?.skills || [];
  return list
    .map((s) => (typeof s === 'string' ? s : s?.skill || s?.canonical_name || s?.name))
    .map((s) => String(s || '').trim())
    .filter(Boolean);
}

/**
 * Target/weak-area prefill for the shared skills field.
 * Prefills only when the user has not explicitly chosen topics;
 * an explicit selection is never overridden. Pure for tests.
 */
export function applyTargetPrefill(currentSkills, requiredSkills, explicit) {
  const current = Array.isArray(currentSkills) ? currentSkills : [];
  const required = (Array.isArray(requiredSkills) ? requiredSkills : [])
    .map((s) => String(s).trim())
    .filter(Boolean);
  if (explicit || required.length === 0) {
    return { skills: current, applied: false };
  }
  return { skills: required.slice(0, 5), applied: true };
}

/**
 * True when a start payload contains interview (free-text) rounds, whose
 * content is resolved server-side per skill. MCQ/SQL/coding availability
 * is already validated pre-commit by POST /session/start itself, so only
 * interview payloads get a pre-start availability probe.
 */
export function payloadHasInterview(payload) {
  const blocks = payload?.blocks;
  if (Array.isArray(blocks)) {
    return blocks.some((b) => b?.round_type === 'technical_short_answer' || b?.category === 'interview');
  }
  if (payload?.round_type === 'technical_short_answer') return true;
  return Array.isArray(payload?.round_plan) && payload.round_plan.includes('technical_short_answer');
}

/**
 * True when a start-failure message carries the server's availability
 * wording (content shortage, not a malformed request). Pure for tests.
 */
export function isAvailabilityMessage(message) {
  return /reviewed|availab|not enough|unknown/i.test(String(message || ''));
}

/**
 * Interview topic options for the given skills, from the practice-bank
 * `interview_topics` metadata ({skill: [topics]}). One block-level topic
 * applies to every selected skill, so only topics shared by ALL skills
 * are offered (intersection, deduplicated and sorted); skills match
 * case-insensitively. Pure.
 */
export function sharedTopicsForSkills(skills, metadata) {
  if (!metadata || typeof metadata !== 'object') return [];
  const wanted = (skills || []).map((s) => String(s).trim().toLowerCase()).filter(Boolean);
  if (wanted.length === 0) return [];
  let shared = null;
  for (const [skill, topics] of Object.entries(metadata)) {
    if (!wanted.includes(String(skill).trim().toLowerCase())) continue;
    const names = new Set(
      (topics || []).map((topic) => String(topic || '').trim()).filter(Boolean)
    );
    shared = shared === null ? names : new Set([...shared].filter((name) => names.has(name)));
  }
  if (shared === null) return [];
  return Array.from(shared).sort((a, b) => a.localeCompare(b));
}

/**
 * Reconcile a selected topic with (possibly changed) skills. Keeps the
 * topic when it is still offered; otherwise clears it so the caller can
 * say so visibly. Pure for tests.
 */
export function reconcileTopic(selected, skills, metadata) {
  const current = typeof selected === 'string' ? selected.trim() : '';
  if (!current) return { topic: '', cleared: false };
  const options = sharedTopicsForSkills(skills, metadata);
  if (options.includes(current)) return { topic: current, cleared: false };
  return { topic: '', cleared: true };
}

/**
 * Explains an empty shared-topic offer for multi-skill selections so the
 * user can split the block or change its scope. Returns null when no
 * explanation applies (single skill, no skills, or options exist). Pure.
 */
export function multiSkillTopicNote(skills, metadata, metadataReady) {
  const list = (skills || []).map((s) => String(s).trim()).filter(Boolean);
  if (!metadataReady || list.length < 2) return null;
  if (sharedTopicsForSkills(list, metadata).length > 0) return null;
  return `No topic is shared by ${list.join(' and ')}. Split into separate blocks, adjust skills, or leave the topic unrestricted.`;
}

/**
 * Summarize a POST /session/availability response for the pre-start
 * notice. Pure for tests. Returns null when everything is available.
 */
export function summarizeAvailability(resp) {
  if (!resp || resp.available !== false) return null;
  const reasons = (resp.blocks || [])
    .filter((b) => b && b.available === false)
    .map((b) => {
      const where = b.position != null ? `Block ${b.position}` : 'This practice';
      const what = (b.skills || []).length ? ` (${b.skills.join(', ')})` : '';
      return `${where}${what}: ${b.reason || 'content unavailable.'}`;
    });
  return {
    title: resp.reviewed_only
      ? 'Assessed practice is unavailable'
      : 'Practice content is unavailable',
    reasons: reasons.length ? reasons : ['The requested content is unavailable.'],
    reviewedOnly: Boolean(resp.reviewed_only),
  };
}
