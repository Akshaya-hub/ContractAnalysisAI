from fastapi import FastAPI
from pydantic import BaseModel
import uuid

app = FastAPI(title="Mock Pipeline", version="0.0.1")

class BaseIn(BaseModel):
    document_id: str | None = None
    tenant_id: str | None = None
    profile: str | None = None
    jurisdiction: str | None = None
    sanitized_path: str | None = None
    filename: str | None = None

@app.post("/ingest")
def ingest(payload: BaseIn):
    return {
        "ingested": True,
        "document_id": payload.document_id or str(uuid.uuid4()),
        "chunks": 10,
        "info": {"filename": payload.filename, "sanitized_path": payload.sanitized_path}
    }

@app.post("/extract")
def extract(prev: dict):
    return {"clauses": ["Confidentiality", "Term", "Termination", "Governing Law"]}

@app.post("/detect")
def detect(prev: dict):
    return {"risks": [{"clause": "Termination", "level": "High", "reason": "5 days notice"}]}

@app.post("/recommend")
def recommend(prev: dict):
    return {"recommendations": [{"clause": "Termination", "suggest": "30 days notice"}]}

@app.post("/render")
def render(prev: dict):
    # pretend a report was generated
    return {"url": "http://localhost:9000/demo-report.pdf"}