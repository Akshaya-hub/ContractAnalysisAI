from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any

app = FastAPI()

# In-memory mock storage
CLAUSE_STORE: Dict[str, List[Dict[str, Any]]] = {}

class Ingested(BaseModel):
    document_id: str
    tenant_id: str
    chunks: List[Dict[str, Any]]  # corrected type

@app.post("/extract")
async def extract(req: Ingested):
    return {
        "document_id": req.document_id,
        "clauses": [
            {
                "type": "Termination",
                "span": {"page": 1, "start": 0, "end": 66},
                "text": "Either party may terminate with 5 days notice.",
                "key_fields": {"notice_period_days": 5, "for_convenience": True},
                "summary": "Termination for convenience with 5 days' notice.",
                "confidence": 0.9
            },
            {
                "type": "Governing Law",
                "span": {"page": 2, "start": 0, "end": 23},
                "text": "State X.",
                "key_fields": {},
                "summary": "Governing law is State X.",
                "confidence": 0.88
            }
        ]
    }

@app.get("/clauses/{doc_id}")
def get_clauses(doc_id: str):
    if doc_id not in CLAUSE_STORE:
        CLAUSE_STORE[doc_id] = [
            {"id": 1, "text": "Payment within 30 days."},
            {"id": 2, "text": "Termination anytime."},
            {"id": 3, "text": "Confidentiality clause."},
        ]
    return CLAUSE_STORE[doc_id]

