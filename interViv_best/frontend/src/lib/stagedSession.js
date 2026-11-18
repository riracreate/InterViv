import {
  activateRound, continueSession, fetchAnswerDraft, fetchAvailability,
  fetchSession, saveAnswerDraft, startSession, submitAnswer,
} from './api.js';

const transport = { activateRound, continueSession, fetchAnswerDraft, fetchAvailability,
  fetchSession, saveAnswerDraft, startSession, submitAnswer };

export function interviewScreenForSession(session) {
  if (session?.flow_version === 'staged_v1') return 'staged';
  return session?.status === 'completed' ? 'dashboard' : 'legacy';
}

export function quickInterviewPayload(form) {
  const skills = [...new Set((form.skills || []).map(s => String(s).trim()).filter(Boolean))];
  if (!skills.length) throw new Error('Select at least one skill.');
  const practiceMode = form.practiceMode === 'assessment' ? 'assessment' : 'coached_practice';
  const payload = {
    flow_version: 'staged_v1', preset: 'quick', skills,
    target_role_id: form.targetRoleId || null,
    target_company_id: form.targetCompanyId || null,
    practice_mode: practiceMode,
    allow_optional_follow_ups: practiceMode !== 'assessment' && Boolean(form.allowOptionalFollowUps),
  };
  if (form.candidateId) payload.candidate_id = form.candidateId;
  return payload;
}

export async function startQuickInterview(form, api = transport) {
  const payload = quickInterviewPayload(form);
  const availability = await api.fetchAvailability(payload);
  if (availability?.available === false) {
    const reasons = (availability.blocks || []).filter(b => b.available === false)
      .map(b => b.reason || 'The requested content is unavailable.');
    const error = new Error(reasons.join(' ') || availability.reason || 'The requested content is unavailable.');
    error.status = 422;
    throw error;
  }
  return api.startSession(payload);
}

// Deliberately omit every evaluation/reference field, including unexpected ones.
function publicTurn(round) {
  if (!round) return null;
  const stage = round.stage || round.config_json?.stage || null;
  return {
    round: Number(round.round),
    type: round.round_type || 'technical_short_answer',
    stage,
    question: String(round.question || round.question_context?.question || ''),
    skill: String(round.skill || ''),
    status: round.status,
    expiresAt: round.expires_at || null,
    startedAt: round.started_at || null,
    isFollowUp: Boolean(round.is_follow_up || stage === 'follow_up'),
    parentRound: round.follow_up_parent_round || round.config_json?.follow_up_parent_round || null,
  };
}

export function stagedSessionState(session) {
  if (!session?.session_id || interviewScreenForSession(session) !== 'staged') {
    throw new Error('This interview is not available on this screen.');
  }
  const active = publicTurn(session.active_round);
  const pending = publicTurn(session.pending_round);
  const submitted = (session.round_history || []).filter(r => r.status === 'submitted');
  let phase = 'unavailable';
  if (session.status === 'completed') phase = 'completed';
  else if (session.status === 'content_blocked') phase = 'blocked';
  else if (active?.status === 'in_progress') phase = 'answering';
  else if (pending?.status === 'ready') phase = 'ready';
  return {
    sessionId: session.session_id, preset: session.preset || 'quick', phase, active, pending,
    totalRounds: Number(session.total_rounds) || 0,
    answeredCount: submitted.length,
    lastSubmittedRound: submitted.at(-1)?.round || null,
    blockedReason: String(session.progression_blocked_reason || 'The next question is unavailable.'),
    stage: active?.stage || pending?.stage || submitted.at(-1)?.stage || null,
    busy: false, needsRefresh: false, error: '',
  };
}

/** Server-owned transitions. Mutation responses never become evaluation UI. */
export function createStagedSessionController({ session, onChange, api = transport }) {
  let state = stagedSessionState(session);
  const sessionId = state.sessionId;
  let disposed = false;
  const publish = () => { if (!disposed) onChange?.({ ...state }); };
  const canonical = async () => {
    const fetched = await api.fetchSession(sessionId);
    if (disposed) return;
    if (fetched?.session_id !== sessionId) throw new Error('The interview response did not match this session. Refresh to retry.');
    state = { ...stagedSessionState(fetched), busy: true };
  };
  const perform = async (action, mutation = true) => {
    if (disposed || state.busy) return false;
    state = { ...state, busy: true, error: '' };
    publish();
    try {
      await action?.();
      await canonical();
      return !disposed;
    } catch (error) {
      // A lost response may follow an accepted submission. Reconcile before
      // offering another POST; never guess whether an answer was saved.
      let reconciled = false;
      if (mutation) {
        try { await canonical(); reconciled = !disposed; } catch { /* explicit refresh required */ }
      }
      state = { ...state, needsRefresh: !reconciled,
        error: error?.message || 'Could not update this interview. Refresh to retry.' };
      return false;
    } finally {
      state = { ...state, busy: false };
      publish();
    }
  };
  return {
    snapshot: () => ({ ...state }),
    refresh: () => perform(null, false),
    submit: answer => {
      if (state.phase !== 'answering' || state.needsRefresh || state.active?.type !== 'technical_short_answer' || !answer.trim()) return Promise.resolve(false);
      const round = state.active.round;
      return perform(() => api.submitAnswer({ session_id: sessionId, round, answer_text: answer }));
    },
    advance: () => {
      if (state.phase !== 'ready' || state.needsRefresh) return Promise.resolve(false);
      return perform(() => api.activateRound(sessionId, state.pending.round));
    },
    retryBlocked: () => {
      if (state.phase !== 'blocked' || state.needsRefresh) return Promise.resolve(false);
      return perform(() => api.continueSession(sessionId));
    },
    readDraft: async round => {
      if (disposed || state.phase !== 'answering' || state.active?.round !== round) return null;
      let draft;
      try {
        draft = await api.fetchAnswerDraft(sessionId, round);
      } catch (error) {
        if (error?.status !== 404) throw error;
      }
      if (disposed || state.phase !== 'answering' || state.active?.round !== round) return null;
      return String(draft?.draft?.answer_text || '');
    },
    saveDraft: async (round, answer) => {
      if (disposed || state.phase !== 'answering' || state.active?.round !== round) return false;
      await api.saveAnswerDraft(sessionId, { round, answer_text: answer });
      return !disposed && state.active?.round === round;
    },
    dispose: () => { disposed = true; },
  };
}
