import { normalizeSessionData } from './roundContractHelpers.js';
import { LEGACY_BUILDER_DRAFT_KEY } from './practiceBuilder.js';
import { loginHref } from './authRedirect.js';
import { createUnauthorizedHandler, unauthorizedRoute } from './authGuard.js';
import { errorFromFetchFailure, kindForStatus, makeRequestError } from './requestErrors.js';
import { clearSessionScopedState } from './accountStorage.js';

const API_BASE_URL = (import.meta.env?.VITE_API_BASE_URL || "").replace(/\/$/, "");
const SESSION_STORAGE_KEY = "adaptive-mock-interview-state";
const AUTH_TOKEN_KEY = "interviv-auth-token";

export function apiErrorMessage(data) {
  const detail = data && data.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const lines = detail.map((item) => {
      if (typeof item === "string") return item;
      if (!item || typeof item !== "object") return "Invalid value";
      const loc = Array.isArray(item.loc) ? item.loc.filter((part) => part !== "body") : [];
      const field = loc.join(".");
      const message = item.msg || item.message || "Invalid value";
      return field ? `${field}: ${message}` : message;
    });
    return lines.filter(Boolean).join("\n") || "Something went wrong";
  }
  return "Something went wrong";
}

export function fetchCodingExecutionStatus() { return request('/problems/execution/status'); }
export function fetchCodingCoach(payload) {
  return request('/problems/coach/hint', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
}

function apiUrl(path) {
  return API_BASE_URL ? `${API_BASE_URL}${path}` : `/api${path}`;
}

function readToken() {
  try {
    return localStorage.getItem(AUTH_TOKEN_KEY);
  } catch {
    return null;
  }
}

/** Status of GET /auth/me for one specific token (no shared side effects). */
async function verifyToken(token) {
  const response = await fetch(apiUrl("/auth/me"), {
    headers: { Authorization: `Bearer ${token}` },
  });
  return response.status;
}

// Confirmed expiry: clear account state once, then go to sign-in without
// leaving the expired page in history.
function expireSession() {
  clearAuthToken();
  if (typeof window === "undefined" || !window.location) return;
  if (window.location.pathname.startsWith("/login")) return;
  const here = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  window.location.replace(loginHref(here, window.location.origin));
}

const handleUnauthorized = createUnauthorizedHandler({
  verifyToken,
  currentToken: readToken,
  onExpired: expireSession,
});

async function request(path, options = {}) {
  const token = readToken();
  const headers = new Headers(options.headers || {});
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  let response;
  try {
    response = await fetch(apiUrl(path), { ...options, headers });
  } catch (err) {
    // Aborts are cancellations; anything else is a retryable network error.
    throw errorFromFetchFailure(err, options.signal);
  }
  const data = await response.json().catch(() => ({}));

  if (response.status === 401 && token) {
    // Never log out on a single 401: confirm with /auth/me (shared across
    // concurrent failures) and ignore responses for a replaced token.
    const route = unauthorizedRoute(path, options.method);
    if (route === "confirmed") {
      if (readToken() === token) expireSession();
    } else if (route === "verify") {
      await handleUnauthorized(token);
    }
  }
  if (!response.ok) {
    throw makeRequestError({
      kind: kindForStatus(response.status),
      status: response.status,
      message: apiErrorMessage(data),
      detail: data.detail,
    });
  }

  return data;
}

// Browser state not keyed by account. Removed whenever the signed-in account
// changes (signin, signup, signout) so it never surfaces under another
// account on a shared browser. Per-account keys are left intact.
function clearUnscopedAccountState() {
  try {
    localStorage.removeItem(SESSION_STORAGE_KEY);
    localStorage.removeItem(LEGACY_BUILDER_DRAFT_KEY);
  } catch { /* storage unavailable */ }
  // Per-account session values (e.g. the upload wizard) never outlive the
  // account that wrote them.
  clearSessionScopedState();
}

export function hasAuthToken() {
  return Boolean(readToken());
}

export function saveAuthToken(token) {
  clearUnscopedAccountState();
  localStorage.setItem(AUTH_TOKEN_KEY, token);
}

export function clearAuthToken() {
  clearUnscopedAccountState();
  try { localStorage.removeItem(AUTH_TOKEN_KEY); } catch { /* storage unavailable */ }
}

/** Sign out: forget the token and every account-sensitive browser value. */
export function signOut() {
  clearAuthToken();
  clearInterviewState();
}

export function signup(payload) {
  return request("/auth/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  }).then(data => {
    if (data.access_token) saveAuthToken(data.access_token);
    return data;
  });
}

export function login(payload) {
  return request("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  }).then(data => {
    if (data.access_token) saveAuthToken(data.access_token);
    return data;
  });
}

export function fetchMe() {
  return request("/auth/me");
}

export function fetchAccountOverview() {
  return request("/dashboard/progress");
}

export function fetchCompanies() {
  return request("/companies");
}

export function fetchCompanyRoles(companyId) {
  return request(`/companies/${encodeURIComponent(companyId)}/roles`);
}

export function fetchGapAnalysis(userId, roleId) {
  return request(`/gap-analysis/${encodeURIComponent(userId)}/${encodeURIComponent(roleId)}`);
}

export function fetchMyGapAnalysis(roleId) {
  return request(`/gap-analysis/me/${encodeURIComponent(roleId)}`);
}

export function fetchRoadmap(userId, roleId, days = 30) {
  return request(`/roadmap/${encodeURIComponent(userId)}/${encodeURIComponent(roleId)}?days=${days}`);
}

export function fetchMyRoadmap(roleId, days = 30) {
  return request(`/roadmap/me/${encodeURIComponent(roleId)}?days=${days}`);
}

export function fetchSkillGraph() {
  return request("/skill-graph/me");
}

export function fetchMastery() {
  return request("/mastery/me");
}

export function fetchLearningSignals() {
  return request("/learning/signals/me");
}

export function fetchPracticeBank() {
  return request("/session/practice-bank");
}

export function fetchResources({ skillId, questionId, limitPerLevel } = {}) {
  const params = new URLSearchParams();
  if (skillId != null && String(skillId).trim() !== "") {
    params.set("skill_id", String(skillId));
  }
  if (questionId != null && String(questionId).trim() !== "") {
    params.set("question_id", String(questionId));
  }
  if (limitPerLevel != null) params.set("limit_per_level", String(limitPerLevel));
  const qs = params.toString();
  return request(`/resources${qs ? `?${qs}` : ""}`);
}

export function scoreAts(payload) {
  return request("/ats/score", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function fetchAtsRuns(limit = 20) {
  return request(`/ats/runs?limit=${encodeURIComponent(limit)}`);
}

export function fetchJobs({ q = "", where = "", page = 1, country = "in", source = "adzuna" } = {}) {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (where) params.set("where", where);
  if (country) params.set("country", country);
  params.set("page", String(page));
  params.set("source", source === "greenhouse" ? "greenhouse" : "adzuna");
  return request(`/jobs?${params.toString()}`);
}

export function fetchJob(jobId) {
  return request(`/jobs/${encodeURIComponent(jobId)}`);
}

export function fetchJobPrepare(jobId, payload = {}) {
  return request(`/jobs/${encodeURIComponent(jobId)}/prepare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function fetchJobPractice(jobId, payload = {}) {
  return request(`/jobs/${encodeURIComponent(jobId)}/practice`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function fetchCoachPlan(payload) {
  return request("/coach/plan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function fetchCoachStartPractice(payload) {
  return request("/coach/start-practice", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function createCoachConversation() {
  return request("/coach/conversations", { method: "POST" });
}

export function fetchCoachConversation(conversationId) {
  return request(`/coach/conversations/${encodeURIComponent(conversationId)}`);
}

export function patchCoachGoals(conversationId, payload) {
  return request(`/coach/conversations/${encodeURIComponent(conversationId)}/goals`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function postCoachMessage(conversationId, payload) {
  return request(`/coach/conversations/${encodeURIComponent(conversationId)}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function ensureStudyPlan(payload) {
  return request("/roadmap/plans/me", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
}

export function completeStudyTask(taskId, payload = {}) {
  return request(`/roadmap/plans/me/tasks/${encodeURIComponent(taskId)}/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function fetchStudyPlan(params = {}) {
  const qs = new URLSearchParams();
  if (params.roleId) qs.set("role_id", params.roleId);
  if (params.confirmedGoal) qs.set("confirmed_goal", params.confirmedGoal);
  const q = qs.toString();
  return request(`/roadmap/plans/me${q ? `?${q}` : ""}`);
}

export function markRoadmapProgress(payload) {
  return request("/learning/roadmap-progress", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function setTargetCompany(targetCompanyId, targetRoleId) {
  return request("/auth/me/target", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      target_company_id: targetCompanyId,
      target_role_id: targetRoleId,
    }),
  });
}

export function fetchTargetContext() {
  return request("/target-context/me");
}

export function saveTargetContext(payload) {
  return request("/target-context/me", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function fetchNotebook() {
  return request("/learning/notebook/me");
}

export function createRetrySet(payload) {
  return request("/learning/retry-sets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function fetchRetrySets() {
  return request("/learning/retry-sets/me");
}

export function fetchRetrySet(setId) {
  return request(`/learning/retry-sets/${encodeURIComponent(setId)}`);
}

export function deleteRetrySet(setId) {
  return request(`/learning/retry-sets/${encodeURIComponent(setId)}`, {
    method: "DELETE",
  });
}

export function startRetrySet(setId) {
  return request(`/learning/retry-sets/${encodeURIComponent(setId)}/start`, {
    method: "POST",
  });
}

export function fetchBookmarks() {
  return request("/learning/bookmarks/me");
}

export function saveBookmark(itemType, itemId) {
  return request("/learning/bookmarks", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ item_type: itemType, item_id: itemId }),
  });
}

export function removeBookmark(itemType, itemId) {
  const params = new URLSearchParams({ item_type: itemType, item_id: itemId });
  return request(`/learning/bookmarks?${params.toString()}`, {
    method: "DELETE",
  });
}

export function fetchHint(itemType, itemId) {
  const params = new URLSearchParams({ item_type: itemType, item_id: itemId });
  return request(`/learning/hint?${params.toString()}`);
}

export function fetchExplanation(itemType, itemId) {
  const params = new URLSearchParams({ item_type: itemType, item_id: itemId });
  return request(`/learning/explanation?${params.toString()}`);
}

export function fetchItemStatus(itemType) {
  const params = new URLSearchParams({ item_type: itemType });
  return request(`/learning/item-status/me?${params.toString()}`);
}

export function fetchNextSteps() {
  return request("/learning/next-steps/me");
}

export function fetchDueReviews() {
  return request("/learning/reviews/due");
}

export function fetchReviewSchedules() {
  return request("/learning/reviews/me");
}

export function syncReviewSchedules() {
  return request("/learning/reviews/sync", { method: "POST" });
}

export function startDueReviews(payload = {}) {
  return request("/learning/reviews/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function uploadResume(file) {
  const formData = new FormData();
  formData.append("file", file);
  return request("/resume", { method: "POST", body: formData });
}

export function startSession(payload) {
  return request("/session/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export function fetchAvailability(payload) {
  return request("/session/availability", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export function submitAnswer(payload) {
  const body = {
    ...payload,
    engagement_label: payload.engagement_label ?? null,
    engagement_confidence: payload.engagement_confidence ?? null,
    engagement_delta: payload.engagement_delta ?? null,
  };
  return request("/session/answer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
}

export function runSqlQuery(payload) {
  return request("/session/sql/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export function runCodingPreview(payload) {
  return request("/session/coding/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export function fetchProblems({ difficulty = "", topic = "" } = {}) {
  const params = new URLSearchParams();
  if (difficulty) params.set("difficulty", difficulty);
  if (topic) params.set("topic", topic);
  const query = params.toString();
  return request(query ? `/problems?${query}` : "/problems");
}

export function fetchProblem(problemId) {
  return request(`/problems/${encodeURIComponent(problemId)}`);
}

export function fetchSession(sessionId) {
  return request(`/session/${encodeURIComponent(sessionId)}`).then(normalizeSessionData);
}

/** Open a prepared round; idempotent (never restarts or extends its clock). */
export function activateRound(sessionId, roundNumber) {
  return request(
    `/session/${encodeURIComponent(sessionId)}/rounds/${encodeURIComponent(roundNumber)}/activate`,
    { method: "POST" }
  );
}

export function continueSession(sessionId) {
  return request(`/session/${encodeURIComponent(sessionId)}/continue`, {
    method: "POST",
  });
}

export function fetchRoundFeedback(sessionId, roundNumber) {
  return request(
    `/session/${encodeURIComponent(sessionId)}/rounds/${encodeURIComponent(roundNumber)}/feedback`
  );
}

export function requestFollowUp(sessionId, parentRound) {
  return request(`/session/${encodeURIComponent(sessionId)}/follow-ups`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      parent_round: parentRound,
      accept_eligibility_consequence: true,
    }),
  });
}

/** Poll while narration is queued/processing; stop on terminal or abort. */
export function narrationIsPending(status) {
  return status === "queued" || status === "processing";
}

export function transcribeAudio(blob, filename = "answer.webm") {
  const formData = new FormData();
  formData.append("audio", blob, filename);
  return request("/transcribe", {
    method: "POST",
    body: formData
  });
}

export function fetchAvCapabilities() {
  return request("/av/capabilities");
}

export function fetchRoleCatalog() {
  return request("/role-practice/catalog");
}

export function planRolePractice(payload) {
  return request("/role-practice/plan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function fetchSystemDesignAttempts() {
  return request("/av/system-design-attempts");
}

export function deleteSystemDesignAttempt(attemptId) {
  return request(`/av/system-design-attempts/${encodeURIComponent(attemptId)}`, {
    method: "DELETE",
  });
}

export function fetchDashboard(sessionId) {
  return request(`/dashboard/${sessionId}`);
}

export function fetchPresets() {
  return request("/practice/presets");
}

export function createPreset(payload) {
  return request("/practice/presets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function fetchPreset(presetId) {
  return request(`/practice/presets/${encodeURIComponent(presetId)}`);
}

export function updatePreset(presetId, payload) {
  return request(`/practice/presets/${encodeURIComponent(presetId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function deletePreset(presetId) {
  return request(`/practice/presets/${encodeURIComponent(presetId)}`, {
    method: "DELETE",
  });
}

export function fetchBuilderDraft() {
  return request("/practice/builder-draft");
}

export function saveBuilderDraft(payload) {
  return request("/practice/builder-draft", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function saveAnswerDraft(sessionId, payload) {
  return request(`/session/${encodeURIComponent(sessionId)}/draft`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function fetchAnswerDraft(sessionId, round) {
  return request(
    `/session/${encodeURIComponent(sessionId)}/draft?round=${encodeURIComponent(round)}`
  );
}

export function buildAnswerMetrics(answer) {
  const wordCount = answer.trim().split(/\s+/).filter(Boolean).length;
  return { word_count: wordCount };
}

export function saveInterviewState(state) {
  localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(state));
}

export function loadInterviewState() {
  try {
    const raw = localStorage.getItem(SESSION_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function clearInterviewState() {
  try { localStorage.removeItem(SESSION_STORAGE_KEY); } catch { /* storage unavailable */ }
}

export function fetchMLAttempts() {
  return request("/ml-primitives/attempts");
}
