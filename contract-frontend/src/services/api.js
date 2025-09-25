import axios from "axios";

const API = axios.create({
  baseURL: "http://127.0.0.1:8000", // always through security_gate
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
  return res.data;
};

export const getRisks = async (docId) => {
  const res = await API.get(`/risks/${docId}`);
  return res.data;
};

export const getRecommendations = async (docId) => {
  const res = await API.get(`/recommend/${docId}`);
  return res.data;
};

  