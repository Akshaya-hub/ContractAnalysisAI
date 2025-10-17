import logging
import os
from typing import Dict, List, Any

import requests
import yaml
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("risk-detector")

app = FastAPI(title="Tenant-Aware Risk Detector")

load_dotenv()

CLAUSE_SERVICE_URL = os.getenv("RISK_DETECTOR__CLAUSE_URL", "http://127.0.0.1:8002").rstrip("/")

# Risk lookup tables keep the service deterministic and offline-friendly.
RISK_PRIORITIES = {
    "Critical": 1,
    "High": 2,
    "Medium": 3,
    "Low": 4,
}

TYPE_DEFAULTS = {
    "Termination": "High",
    "Indemnity": "High",
    "Confidentiality": "Medium",
    "Payment": "Medium",
    "Governing Law": "Low",
}

KEYWORD_RULES: List[tuple[str, str]] = [
    ("automatically renew", "High"),
    ("unlimited liability", "Critical"),
    ("late fee", "Medium"),
    ("arbitration", "Medium"),
    ("exclusive remedy", "High"),
    ("terminate immediately", "High"),
]

RISK_STORE: Dict[str, List[Dict[str, Any]]] = {}


class Clauses(BaseModel):
    document_id: str
    tenant_id: str
    clauses: List[Dict[str, Any]]

# -------------------------------------------------
# Tenant Profile Loader
# -------------------------------------------------
def load_profile(tenant_id: str):
    path = os.path.join("profiles", f"{tenant_id}.yaml")
    if os.path.exists(path):
        with open(path, "r") as f:
            return yaml.safe_load(f)
    return {"tenant_id": tenant_id, "profiles": {}}

# -------------------------------------------------
# Policy Adjustment
# -------------------------------------------------
def choose_default(clause: Dict[str, Any]) -> str:
    ctype = (clause.get("type") or "Unknown").strip()
    return TYPE_DEFAULTS.get(ctype, "Medium")


def apply_keyword_rules(text: str, current: str) -> str:
    lowered = text.lower()
    for keyword, label in KEYWORD_RULES:
        if keyword in lowered and RISK_PRIORITIES[label] < RISK_PRIORITIES[current]:
            return label
    return current


def adjust_with_profile(clause: Dict[str, Any], label: str, profile: Dict[str, Any]) -> str:
    thresholds = profile.get("profiles", {}).get(clause.get("type"), {}).get("thresholds", {})
    key_fields = clause.get("key_fields", {})
    for field, rules in thresholds.items():
        if field not in key_fields:
            continue
        value = key_fields[field]
        if "critical_max" in rules and value > rules["critical_max"]:
            return "Critical"
        if "high_min" in rules and value < rules["high_min"]:
            return "High"
        if "medium_min" in rules and value < rules["medium_min"]:
            return "Medium"
        if "high" in rules and value < rules["high"]:
            return "High"
        if "medium" in rules and value < rules["medium"]:
            return "Medium"
        if "low" in rules and value < rules["low"]:
            return "Low"
    return label


def score_clause(clause: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
    text = (clause.get("text") or "").strip()
    if not text:
        return {
            "clause_id": clause.get("id"),
            "clause_type": clause.get("type", "Unknown"),
            "severity": "Review Needed",
            "issue": "Clause text missing",
            "confidence": 0.0,
            "score": 0.0,
            "evidence_spans": [clause.get("span", {})],
        }

    label = choose_default(clause)
    label = apply_keyword_rules(text, label)
    label = adjust_with_profile(clause, label, profile)

    confidence = {
        "Critical": 0.95,
        "High": 0.85,
        "Medium": 0.65,
        "Low": 0.45,
        "Review Needed": 0.3,
    }.get(label, 0.6)

    return {
        "clause_id": clause.get("id"),
        "clause_type": clause.get("type", "Unknown"),
        "severity": label,
        "score": round(confidence * 10, 2),
        "issue": f"Detected {label} indicators",
        "rationale": "Rule-based assessment with tenant profile overrides",
        "confidence": confidence,
        "evidence_spans": [clause.get("span", {})],
    }


def run_detection(req: Clauses) -> List[Dict[str, Any]]:
    profile = load_profile(req.tenant_id)
    logger.info(
        "🔎 Running risk detection for document %s with %s clauses",
        req.document_id,
        len(req.clauses),
    )

    scored = [score_clause(clause, profile) for clause in req.clauses]
    RISK_STORE[req.document_id] = scored
    logger.info("📦 Stored %s risks for document %s", len(scored), req.document_id)
    return scored

# -------------------------------------------------
# API Endpoints
# -------------------------------------------------
@app.post("/detect")
async def detect(req: Clauses):
    risks = run_detection(req)
    return {"document_id": req.document_id, "risks": risks}

@app.get("/risks/{doc_id}")
def get_risks(doc_id: str, tenant_id: str = "demo"):
    if doc_id not in RISK_STORE:
        try:
            resp = requests.get(f"{CLAUSE_SERVICE_URL}/clauses/{doc_id}", timeout=30)
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)

            data = resp.json()
            if isinstance(data, dict) and "clauses" in data:
                clauses = data["clauses"]
            elif isinstance(data, list):
                clauses = data
            else:
                raise HTTPException(status_code=500, detail=f"Invalid response from clause extractor: {data}")

            req = Clauses(document_id=doc_id, tenant_id=tenant_id, clauses=clauses)
            risks = run_detection(req)
            return {"document_id": doc_id, "risks": risks}

        except Exception as e:
            logger.error(f"❌ Failed to auto-detect risks for {doc_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to auto-detect risks: {str(e)}")

    logger.info(f"📤 Returning cached risks for document {doc_id}")
    return {"document_id": doc_id, "risks": RISK_STORE[doc_id]}

@app.get("/health")
def health():
    return {"status": "ok"}
