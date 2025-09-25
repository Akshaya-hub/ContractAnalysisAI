import os
import uuid
import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# ── service URLs (override in .env or docker-compose)
SECURITY_GATE_URL = os.getenv("SECURITY_GATE_URL", "http://127.0.0.1:8001")
SECURITY_SECRET   = os.getenv("SECURITY_SECRET",   "dev-secret")
INGEST_URL        = os.getenv("INGEST_URL",        "http://127.0.0.1:8002/ingest")
EXTRACT_URL       = os.getenv("EXTRACT_URL",       "http://127.0.0.1:8003/extract")
RISK_URL          = os.getenv("RISK_URL",          "http://127.0.0.1:8004/detect")
RECO_URL          = os.getenv("RECO_URL",          "http://127.0.0.1:8005/recommend")
RENDER_URL        = os.getenv("RENDER_URL",        "http://127.0.0.1:8006/render")

app = FastAPI(title="Orchestrator", version="0.1.1")

# simple in-memory doc store: document_id -> info
DOC_STORE: dict[str, dict] = {}

class AnalyzeReq(BaseModel):
    document_id: str
    tenant_id: str = "demo"
    profile: str = "standard_v1"
    jurisdiction: str | None = None

@app.get("/health")
def health():
    return {"ok": True}

# ── helper to call the security-gate upload
async def security_scan_upload(pdf_bytes: bytes, filename: str) -> dict:
    async with httpx.AsyncClient(timeout=60) as client:
        files = {"file": (filename, pdf_bytes, "application/pdf")}
        headers = {"x-secret": SECURITY_SECRET}
        r = await client.post(f"{SECURITY_GATE_URL}/v1/security/scan-upload",
                              files=files, headers=headers)
        r.raise_for_status()
        return r.json()

# ── 1) Frontend uploads here first
@app.post("/v1/upload")
async def upload_document(file: UploadFile = File(...)):
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(415, "Only PDF files are allowed")
    pdf_bytes = await file.read()

    report = await security_scan_upload(pdf_bytes, file.filename)
    doc_id = report["file_id"]

    DOC_STORE[doc_id] = {
        "filename": file.filename,
        "sanitized_path": report["sanitized_path"],
        "pages": report["pages"],
        "security_report": report,
    }
    # return the new document_id so the client can call /jobs/analyze next
    return {"document_id": doc_id, "security_report": report}

# tiny helper for downstream POSTs
async def _post_json(client: httpx.AsyncClient, url: str, payload: dict) -> dict:
    r = await client.post(url, json=payload)
    r.raise_for_status()
    return r.json()

# ── 2) Then the client calls analyze with the document_id from /v1/upload
@app.post("/jobs/analyze")
async def analyze(req: AnalyzeReq):
    doc = DOC_STORE.get(req.document_id)
    if not doc:
        raise HTTPException(404, "document_id not found. Upload first via /v1/upload.")

    base = {
        "document_id": req.document_id,
        "tenant_id": req.tenant_id,
        "profile": req.profile,
        "jurisdiction": req.jurisdiction,
        "sanitized_path": doc["sanitized_path"],
        "filename": doc["filename"],
    }

    job_id = str(uuid.uuid4())
    async with httpx.AsyncClient(timeout=120) as c:
        try:
            ing     = await _post_json(c, INGEST_URL,  base)
            clauses = await _post_json(c, EXTRACT_URL, ing)
            risks   = await _post_json(c, RISK_URL,    clauses)
            recos   = await _post_json(c, RECO_URL,    risks)
            payload = {"meta": base, **clauses, **risks, **recos}
            report  = await _post_json(c, RENDER_URL,  payload)
        except httpx.HTTPError as e:
            raise HTTPException(503, f"Downstream service error: {e}") from e

    return {"job_id": job_id, "status": "completed", "report_url": report.get("url")}