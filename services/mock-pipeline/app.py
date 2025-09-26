# services/mock-pipeline/app.py
from fastapi import FastAPI
from pydantic import BaseModel
import uuid

app = FastAPI(title="Mock Pipeline")

class BaseIn(BaseModel):
    document_id: str | None = None
    tenant_id: str | None = None
    profile: str | None = None
    jurisdiction: str | None = None
    sanitized_path: str | None = None
    filename: str | None = None

@app.get("/health")
def health():
    return {"ok": True, "service": "mock-pipeline"}

@app.post("/ingest")
def ingest(payload: BaseIn):
    return {
        "document_id": payload.document_id or str(uuid.uuid4()),
        "chunks": 3,
        "info": {"filename": payload.filename, "tenant_id": payload.tenant_id}
    }

@app.post("/extract")
def extract(payload: dict):
    # pretend clause extraction
    return {"clauses": [{"type":"termination","text":"…","confidence":0.92}]}

@app.post("/detect")
def detect(payload: dict):
    # pretend risk detection
    return {"risks": [{"type":"high-liability","score":0.77}]}

@app.post("/recommend")
def recommend(payload: dict):
    # pretend recommendations
    return {"recommendations": [{"action":"add indemnity cap","reason":"…"}]}

@app.post("/render")
def render(payload: dict):
    # pretend report rendering
    return {"url": "http://127.0.0.1:9000/mock-report.pdf"}

from fastapi.responses import RedirectResponse, Response
from pathlib import Path

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)
