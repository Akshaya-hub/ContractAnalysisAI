# services/orchestrator/app.py

import os
import uuid
from typing import Dict, Any, Optional

import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()  # loads services/orchestrator/.env if present

# ── Service URLs (override in .env or docker-compose)
# NOTE: Default Security-Gate is 8000 (you said it's running there).
SECURITY_GATE_URL = os.getenv("SECURITY_GATE_URL", "http://127.0.0.1:8000")
SECURITY_SECRET   = os.getenv("SECURITY_SECRET",   "dev-secret")
INGEST_URL        = os.getenv("INGEST_URL",        "http://127.0.0.1:8002/ingest")
EXTRACT_URL       = os.getenv("EXTRACT_URL",       "http://127.0.0.1:8003/extract")
RISK_URL          = os.getenv("RISK_URL",          "http://127.0.0.1:8004/detect")
RECO_URL          = os.getenv("RECO_URL",          "http://127.0.0.1:8005/recommend")
RENDER_URL        = os.getenv("RENDER_URL",        "http://127.0.0.1:8006/render")

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "15"))

app = FastAPI(title="Orchestrator", version="0.1.2")

# CORS (adjust origins as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple in-memory doc store: document_id -> info
DOC_STORE: Dict[str, Dict[str, Any]] = {}

# Reuse a single AsyncClient for connection pooling
@app.on_event("startup")
async def _startup() -> None:
    app.state.client = httpx.AsyncClient(
        timeout=httpx.Timeout(60.0, connect=10.0),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    )

@app.on_event("shutdown")
async def _shutdown() -> None:
    client: httpx.AsyncClient = app.state.client
    await client.aclose()


class AnalyzeReq(BaseModel):
    document_id: str
    tenant_id: str = "demo"
    profile: str = "standard_v1"
    jurisdiction: Optional[str] = None


@app.get("/", include_in_schema=False)
def root():
    # Friendly redirect to interactive docs
    return RedirectResponse("/docs")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    # Avoid noisy 404s if you don't ship a favicon
    return Response(status_code=204)


@app.get("/health", include_in_schema=False)
async def health():
    # Light health that also pings the security gate
    status: Dict[str, Any] = {"ok": True, "services": {}}
    client: httpx.AsyncClient = app.state.client
    try:
        r = await client.get(f"{SECURITY_GATE_URL}/health")
        status["services"]["security_gate"] = {"ok": r.status_code == 200}
    except Exception as e:
        status["services"]["security_gate"] = {"ok": False, "error": str(e)}
        status["ok"] = False
    return status


async def security_scan_upload(pdf_bytes: bytes, filename: str) -> Dict[str, Any]:
    """Call the security-gate upload endpoint."""
    client: httpx.AsyncClient = app.state.client
    files = {"file": (filename, pdf_bytes, "application/pdf")}
    headers = {"x-secret": SECURITY_SECRET}
    r = await client.post(f"{SECURITY_GATE_URL}/v1/security/scan-upload",
                          files=files, headers=headers)
    r.raise_for_status()
    return r.json()


@app.post("/v1/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Frontend uploads here first. We forward the PDF to security-gate,
    store the returned info in-memory, and return a document_id.
    """
    # quick content-type / size guard
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=415, detail="Only PDF files are allowed")
    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(pdf_bytes) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File too large (> {MAX_UPLOAD_MB} MB)")

    try:
        report = await security_scan_upload(pdf_bytes, file.filename or "upload.pdf")
    except httpx.HTTPStatusError as e:
        # bubble up details from security-gate
        msg = e.response.text
        raise HTTPException(status_code=e.response.status_code, detail=f"security-gate: {msg}") from e
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"security-gate unreachable: {e}") from e

    doc_id = report.get("file_id")
    if not doc_id:
        raise HTTPException(status_code=502, detail="security-gate: missing file_id")

    DOC_STORE[doc_id] = {
        "filename": file.filename,
        "sanitized_path": report.get("sanitized_path"),
        "pages": report.get("pages"),
        "security_report": report,
    }
    return {"document_id": doc_id, "security_report": report}


async def _post_json(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Downstream helper with clear errors."""
    client: httpx.AsyncClient = app.state.client
    r = await client.post(url, json=payload)
    r.raise_for_status()
    try:
        return r.json()
    except ValueError:
        raise HTTPException(status_code=502, detail=f"{url} returned non-JSON")


@app.post("/jobs/analyze")
async def analyze(req: AnalyzeReq):
    """
    Kick off the pipeline (ingest -> extract -> risk -> recommend -> render).
    Requires a prior /v1/upload which created a document_id in DOC_STORE.
    """
    doc = DOC_STORE.get(req.document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="document_id not found. Upload first via /v1/upload.")

    base: Dict[str, Any] = {
        "document_id": req.document_id,
        "tenant_id": req.tenant_id,
        "profile": req.profile,
        "jurisdiction": req.jurisdiction,
        "sanitized_path": doc["sanitized_path"],
        "filename": doc["filename"],
    }

    job_id = str(uuid.uuid4())
    try:
        ing     = await _post_json(INGEST_URL,  base)
        clauses = await _post_json(EXTRACT_URL, ing)
        risks   = await _post_json(RISK_URL,    clauses)
        recos   = await _post_json(RECO_URL,    risks)
        payload = {"meta": base, **clauses, **risks, **recos}
        report  = await _post_json(RENDER_URL,  payload)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code,
                            detail=f"Downstream error from {e.request.url}: {e.response.text}") from e
    except httpx.HTTPError as e:
        raise HTTPException(status_code=503, detail=f"Downstream service unreachable: {e}") from e

    return {"job_id": job_id, "status": "completed", "report_url": report.get("url")}
