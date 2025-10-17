import axios from "axios";
import { getToken } from "./auth";

const SECURITY_GATE_BASE =
  import.meta.env.VITE_SECURITY_GATE_URL || "http://127.0.0.1:8000";

const API = axios.create({
  baseURL: SECURITY_GATE_BASE,
});

API.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Existing
export const uploadContract = async (file) => {
  const formData = new FormData();
  formData.append("file", file);
  const res = await API.post("/sanitize", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
};

export const ingestContract = async (document_id, tenant_id = "demo_tenant") => {
  const payload = { document_id, tenant_id };
  const res = await API.post("/ingest", payload);
  return res.data;
};

// New analysis endpoints
export const getClauses = async (docId) => {
  const res = await API.get(`/clauses/${docId}`);
  const data = res.data;
  if (Array.isArray(data)) return data;
  return data?.clauses ?? [];
};

export const getRisks = async (docId) => {
  const res = await API.get(`/risks/${docId}`);
  const data = res.data;
  if (Array.isArray(data)) return data;
  return data?.risks ?? [];
};

export const getRecommendations = async (docId) => {
  const res = await API.get(`/recommend/${docId}`);
  const data = res.data;
  if (Array.isArray(data)) return data;
  return data?.recommendations ?? data ?? [];
};

export const chatWithAgent = async (docId, question) => {
  const res = await API.post("/chat", { document_id: docId, question });
  return res.data;
};

export async function makeReport(payload) {
  try {
    const res = await API.post(`/render`, payload);
    return res.data;
  } catch (err) {
    console.error("Error making report:", err);
    throw err;
  }
}
