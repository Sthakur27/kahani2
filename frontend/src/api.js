// Thin wrapper around the Flask API. In dev, Vite proxies /api -> :5051.
const BASE = "/api";

// Auth: a signed session token issued at login/signup is sent as a Bearer
// header. The server derives the user from the verified token — the client no
// longer asserts a user id. `setAuthToken` is called by the auth context.
let authToken = null;
export function setAuthToken(token) {
  authToken = token || null;
}

// Optional hook so the app can react to a 401 (e.g. expired token → log out).
let onUnauthorized = null;
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

async function request(path, opts = {}) {
  const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
  if (authToken) headers.Authorization = `Bearer ${authToken}`;
  const res = await fetch(BASE + path, { ...opts, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err = new Error(body.error || `HTTP ${res.status}`);
    err.status = res.status;
    if (res.status === 401 && onUnauthorized) onUnauthorized();
    throw err;
  }
  return res;
}

async function http(path, opts = {}) {
  return (await request(path, opts)).json();
}

// For paginated endpoints: returns { items, total } (total from X-Total-Count).
async function httpWithTotal(path, opts = {}) {
  const res = await request(path, opts);
  const items = await res.json();
  const total = Number(res.headers.get("X-Total-Count") ?? items.length);
  return { items, total };
}

function qs(params) {
  const p = Object.entries(params)
    .filter(([, v]) => v != null && v !== "")
    .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
    .join("&");
  return p ? `?${p}` : "";
}

// --- auth ---
export const signup = (username, password) =>
  http("/auth/signup", { method: "POST", body: JSON.stringify({ username, password }) });
export const login = (username, password) =>
  http("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) });

// --- admin ---
export const generateDaily = () =>
  http("/admin/generate-daily", { method: "POST" });

// --- stories ---
export const getStories = () => http("/stories"); // first page, array
export const getStoriesPage = ({ rating, genre, limit, offset } = {}) =>
  httpWithTotal("/stories" + qs({ rating, genre, limit, offset })); // { items, total }
export const getStory = (id) => http(`/stories/${id}`);
export const getStoryTree = (storyId) => http(`/stories/${storyId}/tree`);

// --- nodes ---
export const getNodes = (storyId, parentId) =>
  http(`/stories/${storyId}/nodes` + qs({ parent_id: parentId })); // array, first page
export const getNodesPage = (storyId, parentId, { limit, offset } = {}) =>
  httpWithTotal(`/stories/${storyId}/nodes` + qs({ parent_id: parentId, limit, offset }));
export const getNode = (id) => http(`/nodes/${id}`);
export const getNodePath = (id) => http(`/nodes/${id}/path`);
export const createNode = (storyId, data) =>
  http(`/stories/${storyId}/nodes`, { method: "POST", body: JSON.stringify(data) });
export const voteNode = (id, value) =>
  http(`/nodes/${id}/vote`, { method: "POST", body: JSON.stringify({ value }) });
export const draftNode = (data) =>
  http(`/ai/draft`, { method: "POST", body: JSON.stringify(data) });

// --- leaderboard ---
export const getLeaderboard = (limit) => http("/leaderboard" + qs({ limit }));

// --- me (profile/history) ---
export const getMyViews = () => http("/me/views");
export const getMyVotes = () => http("/me/votes");
export const getMyNodes = () => http("/me/nodes");

// --- campaign runs (RPG) ---
export const getStoryCharacters = (storyId) => http(`/stories/${storyId}/characters`);
export const getMyRuns = () => http("/me/runs");
export const startRun = (storyId, body = {}) =>
  http(`/stories/${storyId}/runs`, { method: "POST", body: JSON.stringify(body) });
export const getRun = (runId) => http(`/runs/${runId}`);
export const getRunSummary = (runId) => http(`/runs/${runId}/summary`);
export const takeEdge = (runId, edgeId) =>
  http(`/runs/${runId}/take/${edgeId}`, { method: "POST" });
