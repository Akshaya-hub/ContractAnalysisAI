from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
import os, json, pdfplumber, re
import tiktoken

INDEX_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "storage", "uploads_index.json"))
enc = tiktoken.get_encoding("cl100k_base")

app = FastAPI()

class IngestReq(BaseModel):
    document_id: str
    tenant_id: str
    profile: str | None = None
    jurisdiction: str | None = None

def read_index() -> Dict[str, str]:
    if not os.path.exists(INDEX_PATH):
        return {}
    try:
        return json.load(open(INDEX_PATH, "r", encoding="utf-8"))
    except Exception:
        return {}

def token_chunks(text: str, max_tokens=900, overlap=120) -> List[str]:
    toks = enc.encode(text)
    out, i = [], 0
    while i < len(toks):
        j = min(i + max_tokens, len(toks))
        out.append(enc.decode(toks[i:j]))
        i = j - overlap
        if i < 0: i = 0
    return out

def extract_pdf_text(path: str) -> List[Dict[str, Any]]:
    chunks = []
    with pdfplumber.open(path) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            txt = page.extract_text() or ""
            txt = re.sub(r"[ \t]+", " ", txt)  # normalize spaces
            txt = txt.strip()
            if not txt:
                continue
            # split per page into token-aware chunks
            for segment in token_chunks(txt, max_tokens=900, overlap=120):
                chunks.append({"page": page_no, "text": segment})
    return chunks

def simple_metadata(text0: str) -> Dict[str, Any]:
    # quick-and-dirty metadata heuristics
    parties = re.findall(r"\bbetween\b\s+(.+?)\s+and\s+(.+?)\b", text0, flags=re.IGNORECASE)
    date = re.search(r"\b(20\d{2}|19\d{2})\b", text0)
    return {
        "type": "Unknown",
        "parties": list(parties[0]) if parties else [],
        "date": date.group(0) if date else None
    }

@app.post("/ingest")
async def ingest(req: IngestReq):
    idx = read_index()
    path = idx.get(req.document_id)
    if not path or not os.path.exists(path):
        raise HTTPException(404, f"File for document_id {req.document_id} not found. Upload via /sanitize first.")

    if path.lower().endswith(".pdf"):
        chunks = extract_pdf_text(path)
        # build metadata from first page text if present
        first_text = chunks[0]["text"] if chunks else ""
        meta = simple_metadata(first_text) | {"source_path": path}
    else:
        raise HTTPException(400, "Only PDF supported in this minimal demo.")

    return {
        "document_id": req.document_id,
        "tenant_id": req.tenant_id,
        "chunks": chunks[:50],  # cap for demo
        "metadata": meta
    }
