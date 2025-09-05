from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any

app = FastAPI()

class Risks(BaseModel):
    document_id: str
    risks: List[Dict[str, Any]]

@app.post("/recommend")
async def recommend(req: Risks):
    recos = []
    for r in req.risks:
        if r["clause_type"] == "Termination":
            recos.append({
                "target_clause": "Termination",
                "action": "Replace",
                "suggested_text": "Either party may terminate for convenience with at least 30 days’ prior written notice.",
                "priority": "P0",
                "citations": [{"source": "PolicyKB:v1", "section": "Termination/Notice"}],
                "diff": "++ set notice >= 30 days"
            })
        if r["clause_type"] == "Indemnity":
            recos.append({
                "target_clause": "Indemnity",
                "action": "Add",
                "suggested_text": "Each party shall indemnify and hold harmless the other from third-party claims, subject to liability caps.",
                "priority": "P0",
                "citations": [{"source": "PolicyKB:v1", "section": "Indemnity/Standard"}],
                "diff": "++ add mutual indemnity with caps"
            })
    return {"document_id": req.document_id, "recommendations": recos}
