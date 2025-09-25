from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any

app = FastAPI()

# ----------------------------
# Data Models
# ----------------------------
class RiskItem(BaseModel):
    clause_type: str
    description: str | None = None  # optional extra field if you want

class Risks(BaseModel):
    document_id: str
    risks: List[RiskItem]

# ----------------------------
# In-memory storage
# ----------------------------
RECOMMEND_STORE: Dict[str, List[Dict[str, Any]]] = {}

# ----------------------------
# Endpoints
# ----------------------------
@app.post("/recommend")
async def recommend(req: Risks):
    recos = []
    for r in req.risks:
        if r.clause_type == "Termination":
            recos.append({
                "target_clause": "Termination",
                "action": "Replace",
                "suggested_text": "Either party may terminate for convenience with at least 30 days’ prior written notice.",
                "priority": "P0",
                "citations": [{"source": "PolicyKB:v1", "section": "Termination/Notice"}],
                "diff": "++ set notice >= 30 days"
            })
        elif r.clause_type == "Indemnity":
            recos.append({
                "target_clause": "Indemnity",
                "action": "Add",
                "suggested_text": "Each party shall indemnify and hold harmless the other from third-party claims, subject to liability caps.",
                "priority": "P0",
                "citations": [{"source": "PolicyKB:v1", "section": "Indemnity/Standard"}],
                "diff": "++ add mutual indemnity with caps"
            })

    return {"document_id": req.document_id, "recommendations": recos}


@app.get("/recommend/{doc_id}")
def get_recommend(doc_id: str):
    if doc_id not in RECOMMEND_STORE:
        RECOMMEND_STORE[doc_id] = [
            {"clause_id": 2, "suggestion": "Limit termination to specific conditions."},
            {"clause_id": 3, "suggestion": "Clarify confidentiality duration."},
        ]
    return RECOMMEND_STORE[doc_id]
