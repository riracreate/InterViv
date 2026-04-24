const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
const SESSION_STORAGE_KEY = "adaptive-mock-interview-state";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.detail || "Request failed.");
  }

  return data;
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
  return request("/session/answer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
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
