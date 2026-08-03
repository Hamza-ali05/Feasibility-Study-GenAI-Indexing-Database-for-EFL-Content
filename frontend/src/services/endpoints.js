
import apiClient, { API_URL } from "./apiClient";
import { writeToken } from "services/authStorage";

export async function searchResources(payload) {
  const { data } = await apiClient.post("/api/search/", payload);
  return data;
}

export async function getSearchFacets() {
  const { data } = await apiClient.get("/api/search/facets");
  return data;
}

export async function getSuggestions(q) {
  const { data } = await apiClient.get("/api/search/suggest", {
    params: { q: q || "" },
  });
  return data;
}

export async function getPipelineStatus() {
  const { data } = await apiClient.get("/api/pipeline/status");
  return data;
}

export async function runPipelineStage(name) {
  const encoded = encodeURIComponent(String(name).replace(/ /g, "-"));
  const { data } = await apiClient.post(`/api/pipeline/run/${encoded}`);
  return data;
}

export async function runAllPipeline() {
  const { data } = await apiClient.post("/api/pipeline/run-all");
  return data;
}

export async function resetPipelineStage(name) {
  const encoded = encodeURIComponent(String(name).replace(/ /g, "-"));
  const { data } = await apiClient.post(`/api/pipeline/reset/${encoded}`);
  return data;
}

export async function resetAllPipeline() {
  const { data } = await apiClient.post("/api/pipeline/reset-all");
  return data;
}

export async function getPipelineArtifact(slug) {
  const { data } = await apiClient.get(`/api/pipeline/artifact/${slug}`);
  return data;
}

export async function getMetrics() {
  const { data } = await apiClient.get("/api/metrics/");
  return data;
}

export async function getExplainGlobal() {
  const { data } = await apiClient.get("/api/explain/global");
  return data;
}

export async function getExplainLocal() {
  const { data } = await apiClient.get("/api/explain/local");
  return data;
}

export async function getExplainQuality() {
  const { data } = await apiClient.get("/api/explain/quality");
  return data;
}

export async function askQuestion(question, topK = 5) {
  const { data } = await apiClient.post("/api/qa/ask", {
    question,
    top_k: topK,
  });
  return data;
}

export function getAskStreamUrl(question, topK = 5) {
  const base = (API_URL || "http://localhost:8000").replace(/\/$/, "");
  const params = new URLSearchParams({
    question: question || "",
    top_k: String(topK),
  });
  return `${base}/api/qa/ask-stream?${params.toString()}`;
}

export async function getRecommendations(resourceId, topK = 6) {
  const { data } = await apiClient.get(`/api/recommend/${resourceId}`, {
    params: { top_k: topK },
  });
  return data;
}

export async function uploadResource(formDataOrJson) {
  const isForm = typeof FormData !== "undefined" && formDataOrJson instanceof FormData;
  const { data } = await apiClient.post(
    "/api/analyzer/upload",
    formDataOrJson,
    isForm ? {} : { headers: { "Content-Type": "application/json" } }
  );
  return data;
}

export async function confirmDuplicateUpload(payload) {
  const { data } = await apiClient.post("/api/analyzer/confirm-duplicate", payload);
  return data;
}

export async function patchResourceLabels(resourceId, payload) {
  const { data } = await apiClient.patch(`/api/resources/${resourceId}`, payload);
  return data;
}

export async function getDashboardSummary() {
  const { data } = await apiClient.get("/api/dashboard/summary");
  return data;
}

export async function getAnalyticsSummary() {
  const { data } = await apiClient.get("/api/analytics/summary");
  return data;
}

export async function getSearchesPerDay(days = 14) {
  const { data } = await apiClient.get("/api/analytics/searches-per-day", {
    params: { days },
  });
  return data;
}

export async function getDuplicates() {
  const { data } = await apiClient.get("/api/duplicates");
  return data;
}

export async function resolveDuplicate(payload) {
  const { data } = await apiClient.post("/api/duplicates/resolve", payload);
  return data;
}

export async function rescanDuplicates() {
  const { data } = await apiClient.post("/api/duplicates/rescan");
  return data;
}

export async function getResources(params = {}) {
  const { data } = await apiClient.get("/api/resources/", { params });
  return data;
}

export async function getResourceDetail(id) {
  const { data } = await apiClient.get(`/api/resources/${id}`);
  return data;
}

export async function markResourceViewed(id) {
  await apiClient.get(`/api/resources/${id}/view`);
  return null;
}

export async function deleteResource(id) {
  const { data } = await apiClient.delete(`/api/resources/${id}`);
  return data;
}

export async function adminLogin(username, password) {
  const { data } = await apiClient.post("/api/admin/login", {
    username,
    password,
  });
  if (data && data.access_token) {
    writeToken(data.access_token);
  }
  return data;
}

export async function adminMe() {
  const { data } = await apiClient.get("/api/admin/me");
  return data;
}

export async function adminOverview() {
  const { data } = await apiClient.get("/api/admin/overview");
  return data;
}

export async function getAdminLogs(lines = 200) {
  const { data } = await apiClient.get("/api/admin/logs", {
    params: { lines },
  });
  return data;
}

export async function adminRunPipelineStage(name) {
  const encoded = encodeURIComponent(String(name).replace(/ /g, "-"));
  const { data } = await apiClient.post(`/api/admin/pipeline/run/${encoded}`);
  return data;
}

export async function adminRunAllPipeline() {
  const { data } = await apiClient.post("/api/admin/pipeline/run-all");
  return data;
}

export async function adminResetPipelineStage(name) {
  const encoded = encodeURIComponent(String(name).replace(/ /g, "-"));
  const { data } = await apiClient.post(`/api/admin/pipeline/reset/${encoded}`);
  return data;
}

export async function adminResetAllPipeline() {
  const { data } = await apiClient.post("/api/pipeline/reset-all");
  return data;
}

export async function adminDeleteResource(id) {
  const { data } = await apiClient.delete(`/api/admin/resources/${id}`);
  return data;
}
