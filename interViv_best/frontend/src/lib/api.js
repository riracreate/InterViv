import { normalizeSessionData } from './roundContractHelpers.js';

const API_BASE_URL = (import.meta.env?.VITE_API_BASE_URL || "").replace(/\/$/, "");
const SESSION_STORAGE_KEY = "adaptive-mock-interview-state";
const AUTH_TOKEN_KEY = "interviv-auth-token";

async function request(path, options = {}) {
  const requestPath = API_BASE_URL ? `${API_BASE_URL}${path}` : `/api${path}`;
  const token = localStorage.getItem(AUTH_TOKEN_KEY);
  const headers = new Headers(options.headers || {});
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(requestPath, { ...options, headers });
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const error = new Error(data.detail || data.error || "Request failed.");
    error.status = response.status;
    throw error;
  }

  return data;
}

export function saveAuthToken(token) {
  localStorage.setItem(AUTH_TOKEN_KEY, token);
}

export function clearAuthToken() {
  localStorage.removeItem(AUTH_TOKEN_KEY);
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

export function fetchResources({ skillId, questionId } = {}) {
  const params = new URLSearchParams();
  if (skillId != null && String(skillId).trim() !== "") {
    params.set("skill_id", String(skillId));
  }
  if (questionId != null && String(questionId).trim() !== "") {
    params.set("question_id", String(questionId));
  }
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

export function fetchJobs({ q = "", where = "", page = 1 } = {}) {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (where) params.set("where", where);
  params.set("page", String(page));
  return request(`/jobs?${params.toString()}`);
}

export function fetchJob(jobId) {
  return request(`/jobs/${encodeURIComponent(jobId)}`);
}

export function fetchJobPractice(jobId) {
  return request(`/jobs/${encodeURIComponent(jobId)}/practice`, {
    method: "POST",
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
  const raw = localStorage.getItem(SESSION_STORAGE_KEY);
  return raw ? JSON.parse(raw) : null;
}

export function clearInterviewState() {
  localStorage.removeItem(SESSION_STORAGE_KEY);
}
