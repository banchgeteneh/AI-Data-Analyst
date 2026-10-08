import axios from "axios";

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api/v1",
});

export function setAuthToken(token) {
  if (token) {
    apiClient.defaults.headers.common.Authorization = `Bearer ${token}`;
  } else {
    delete apiClient.defaults.headers.common.Authorization;
  }
}

export async function getDatasetAnalysis(datasetId) {
  const { data } = await apiClient.get(`/datasets/${datasetId}/analysis`);
  return data;
}

export async function getDatasetExplorationCapabilities(datasetId) {
  const { data } = await apiClient.get(`/datasets/${datasetId}/explore/capabilities`);
  return data;
}

export async function exploreDataset(datasetId, payload) {
  const { data } = await apiClient.post(`/datasets/${datasetId}/explore`, payload);
  return data;
}

export function getDashboardData(analysis) {
  return analysis?.dashboard ?? null;
}
