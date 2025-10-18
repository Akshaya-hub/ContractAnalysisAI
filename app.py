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
    for idx, r in enumerate(req.risks, start=1):
        if r.clause_type == "Termination":
            recos.append({
                "clause_id": idx,
                "original_text": "Either party may terminate immediately.",  # mock original
                "suggested_text": "Either party may terminate for convenience with at least 30 days’ prior written notice.",
                "diff": "++ set notice >= 30 days",
                "why": "Ensures fairness by giving both parties preparation time.",
                "priority": "P0",
                "citations": [{"source": "PolicyKB:v1", "section": "Termination/Notice"}],
            })
        elif r.clause_type == "Indemnity":
            recos.append({
                "clause_id": idx,
                "original_text": "Party A indemnifies Party B.",
                "suggested_text": "Each party shall indemnify and hold harmless the other from third-party claims, subject to liability caps.",
                "diff": "++ add mutual indemnity with caps",
                "why": "Balances liability fairly between both parties.",
                "priority": "P0",
                "citations": [{"source": "PolicyKB:v1", "section": "Indemnity/Standard"}],
            })

    RECOMMEND_STORE[req.document_id] = recos
    return {"document_id": req.document_id, "recommendations": recos}


@app.get("/recommend/{doc_id}")
def get_recommend(doc_id: str):
    if doc_id not in RECOMMEND_STORE:
        # fallback mock data
        RECOMMEND_STORE[doc_id] = [
            {
                "clause_id": 2,
                "original_text": "Either party may terminate immediately.",
                "suggested_text": "Either party may terminate with 30 days’ notice.",
                "diff": "++ add notice requirement",
                "why": "Gives parties a fair exit period.",
                "priority": "P1",
                "citations": [],
            },
            {
                "clause_id": 3,
                "original_text": "Confidentiality applies indefinitely.",
                "suggested_text": "Confidentiality applies for 3 years post-termination.",
                "diff": "++ add 3-year limit",
                "why": "Prevents unreasonable indefinite obligations.",
                "priority": "P2",
                "citations": [],
            },
        ]
    return RECOMMEND_STORE[doc_id]
