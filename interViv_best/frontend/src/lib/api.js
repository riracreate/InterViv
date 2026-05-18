const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
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
    throw new Error(data.detail || data.error || "Request failed.");
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

export function fetchSkillGraph(userId) {
  return request(`/skill-graph/${encodeURIComponent(userId)}`);
}

export function fetchMastery(userId) {
  return request(`/mastery/${encodeURIComponent(userId)}`);
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

export function transcribeAudio(blob, filename = "answer.webm") {
  const formData = new FormData();
  formData.append("audio", blob, filename);
  return request("/transcribe", {
    method: "POST",
    body: formData
  });
}

export function fetchDashboard(sessionId) {
  return request(`/dashboard/${sessionId}`);
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
