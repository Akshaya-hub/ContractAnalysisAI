import os
import re
from typing import List, Dict, Any

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Clause Extractor Service")

load_dotenv()

# --------- In-Memory Store ----------
CLAUSE_STORE: Dict[str, List[Dict[str, Any]]] = {}

# --------- Request Models ----------
class Ingested(BaseModel):
    document_id: str
    tenant_id: str
    chunks: List[Dict[str, Any]]  # [{ "page": int, "text": str }]
    metadata: Dict[str, Any] | None = None

INGEST_SERVICE_URL = os.getenv("CLAUSE_EXTRACTOR__INGEST_URL", "http://localhost:8001").rstrip("/")

# --------- Clause Patterns (rule-based demo) ----------
CLAUSE_PATTERNS = {
    "Termination": re.compile(r"(terminate|termination)", re.IGNORECASE),
    "Payment": re.compile(r"(payment|pay within|fees?)", re.IGNORECASE),
    "Confidentiality": re.compile(r"(confidential|non-disclosure|nda)", re.IGNORECASE),
    "Governing Law": re.compile(r"(law|jurisdiction|governed by)", re.IGNORECASE),
}

# --------- Core Extract Function ----------
def run_extraction(req: Ingested):
    clauses = []
    clause_id = 1

    for chunk in req.chunks:
        page = chunk.get("page")
        text = chunk.get("text", "")

        for clause_type, pattern in CLAUSE_PATTERNS.items():
            if pattern.search(text):
                clauses.append({
                    "id": clause_id,
                    "type": clause_type,
                    "span": {"page": page, "start": 0, "end": len(text)},
                    "text": text.strip(),
                    "key_fields": {},
                    "summary": f"Detected {clause_type} clause.",
                    "confidence": 0.75
                })
                clause_id += 1

    CLAUSE_STORE[req.document_id] = clauses
    return {
        "document_id": req.document_id,
        "tenant_id": req.tenant_id,
        "clauses": clauses
    }

# --------- Extract Endpoint ----------
@app.post("/extract")
async def extract(req: Ingested):
    return run_extraction(req)

# --------- Retrieval Endpoint (auto ingest+extract) ----------
@app.get("/clauses/{doc_id}")
def get_clauses(doc_id: str, tenant_id: str = "demo"):
    if doc_id not in CLAUSE_STORE:
        # Auto call ingest service
        try:
            resp = requests.post(
                f"{INGEST_SERVICE_URL}/ingest",
                json={"document_id": doc_id, "tenant_id": tenant_id},
                timeout=30
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)

            ingest_data = resp.json()
            return run_extraction(Ingested(**ingest_data))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to ingest & extract: {str(e)}")

    return CLAUSE_STORE[doc_id]

# --------- Optional Shortcut ----------
@app.post("/extract_from_ingest/{doc_id}")
def extract_from_ingest(doc_id: str, tenant_id: str = "demo"):
    try:
        resp = requests.post(
            f"{INGEST_SERVICE_URL}/ingest",
            json={"document_id": doc_id, "tenant_id": tenant_id},
            timeout=30
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)

        ingest_data = resp.json()
        return run_extraction(Ingested(**ingest_data))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch from ingest: {str(e)}")
