import axios from "axios";

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
  headers: { "Content-Type": "application/json" },
  timeout: 35 * 60 * 1000, // 35 minutes
});

export const startScan = async (url) => {
  const response = await apiClient.post("/scan", { url });
  return response.data;
};

export const analyzeSite = async (url, jsRender = false) => {
  const response = await apiClient.post("/analyze", { url, js_render: jsRender });
  return response.data; // { job_id }
};

export const getJobStatus = async (jobId) => {
  const response = await apiClient.get(`/job/${jobId}`);
  return response.data;
};

/**
 * User-initiated: POST /job/{jobId}/ai
 * Backend caches result — safe to call multiple times.
 */
export const requestAiInsights = async (jobId) => {
  const response = await apiClient.post(`/job/${jobId}/ai`);
  return response.data; // { ai_insights } | { ai_error }
};

export const stopScan = async () => {
  const response = await apiClient.post("/stop");
  return response.data;
};

export default apiClient;