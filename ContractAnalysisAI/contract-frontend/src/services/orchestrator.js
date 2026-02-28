import axios from "axios";
import { getToken } from "./auth";

const ORCH_BASE = import.meta.env.VITE_ORCHESTRATOR_URL || "http://127.0.0.1:8008";

const client = axios.create({
  baseURL: ORCH_BASE,
});

client.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export async function login(username, password) {
  const res = await client.post("/login", { username, password });
  return res.data;
}

export async function orchestrate(documentId, tenantId = "demo") {
  const res = await client.post("/orchestrate", {
    document_id: documentId,
    tenant_id: tenantId,
    job_type: "analysis",
  });
  return res.data;
}

export async function getJobStatus(jobId) {
  const res = await client.get(`/job_status/${jobId}`);
  return res.data;
}

export async function pollJob(jobId, { intervalMs = 1500, timeoutMs = 60000 } = {}) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const status = await getJobStatus(jobId);
    if (status.status === "completed" || status.status === "failed") {
      return status;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new Error("Job polling timed out");
}
