from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException

app = FastAPI(title="Risk Detector Service")
class Clauses(BaseModel):
    document_id: str
    clauses: List[Dict[str, Any]]

RISK_STORE = {}

@app.post("/detect")
async def detect(req: Clauses):
    risks = []
    for c in req.clauses:
        if c["type"] == "Termination" and c.get("key_fields", {}).get("notice_period_days", 0) < 30:
            risks.append({
                "clause_type": "Termination",
                "severity": "High",
                "likelihood": "Medium",
                "score": 7.5,
                "issue": "Short termination notice (5 days).",
                "evidence_spans": [c["span"]],
                "rationale": "Policy requires >=30 days.",
                "confidence": 0.85
            })
    # Example missing indemnity risk
    if not any(c.get("type") == "Indemnity" for c in req.clauses):
        risks.append({
            "clause_type": "Indemnity",
            "severity": "Critical",
            "likelihood": "Medium",
            "score": 8.5,
            "issue": "No indemnity clause found.",
            "evidence_spans": [],
            "rationale": "Standard mutual indemnity missing.",
            "confidence": 0.8
        })
    return {"document_id": req.document_id, "risks": risks}
