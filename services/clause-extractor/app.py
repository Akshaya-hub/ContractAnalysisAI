from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any

app = FastAPI()

class Ingested(BaseModel):
    document_id: str
    tenant_id: str
    chunks: List[Dict,]

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
