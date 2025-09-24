from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any

app = FastAPI()

class IngestReq(BaseModel):
    document_id: str
    tenant_id: str
    profile: str | None = None
    jurisdiction: str | None = None

@app.post("/ingest")
async def ingest(req: IngestReq):
    # TODO: parse PDF/DOCX, chunk, embed, index
    # For demo, return a tiny mock "doc" with two clauses worth of text.
    return {
        "document_id": req.document_id,
        "tenant_id": req.tenant_id,
        "chunks": [
            {"page": 1, "text": "Termination: Either party may terminate with 5 days notice."},
            {"page": 2, "text": "Governing Law: State X."}
        ],
        "metadata": {"type": "NDA", "parties": ["A", "B"], "date": "2024-01-02"}
    }

