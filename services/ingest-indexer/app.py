from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
from pathlib import Path
import os, json, pdfplumber, re, tiktoken

# -----------------------------
# Config
# -----------------------------
UPLOADS_DIR = Path(__file__).parent.parent / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
INDEX_PATH = Path(__file__).parent.parent / "storage" / "uploads_index.json"
INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)

enc = tiktoken.get_encoding("cl100k_base")

app = FastAPI(title="PDF Ingestor")

# -----------------------------
# Models
# -----------------------------
class IngestReq(BaseModel):
    document_id: str
    tenant_id: str
    profile: str | None = None
    jurisdiction: str | None = None

# -----------------------------
# Helpers
# -----------------------------
def read_index() -> Dict[str, str]:
    if not INDEX_PATH.exists():
        return {}
    try:
        return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def write_index(idx: Dict[str, str]):
    INDEX_PATH.write_text(json.dumps(idx, indent=2), encoding="utf-8")

# -----------------------------
# Memory-safe token chunks
# -----------------------------
def token_chunks(text: str, max_tokens=900, overlap=120):
    toks = enc.encode(text)
    i = 0
    while i < len(toks):
        j = min(i + max_tokens, len(toks))
        yield enc.decode(toks[i:j])
        i = j - overlap
        if i < 0:
            i = 0

# -----------------------------
# Memory-safe PDF extraction (generator)
# -----------------------------
def extract_pdf_text(path: Path):
    """Yield PDF chunks one by one"""
    with pdfplumber.open(path) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            txt = page.extract_text() or ""
            txt = re.sub(r"[ \t]+", " ", txt).strip()
            if not txt:
                continue
            for segment in token_chunks(txt):
                yield {"page": page_no, "text": segment}

# -----------------------------
# Metadata extraction
# -----------------------------
def simple_metadata(text0: str) -> Dict[str, Any]:
    parties = re.findall(r"\bbetween\b\s+(.+?)\s+and\s+(.+?)\b", text0, flags=re.IGNORECASE)
    date = re.search(r"\b(20\d{2}|19\d{2})\b", text0)
    return {
        "type": "Unknown",
        "parties": list(parties[0]) if parties else [],
        "date": date.group(0) if date else None
    }

# -----------------------------
# Endpoints
# -----------------------------
@app.post("/sanitize")
async def sanitize(file: UploadFile = File(...), document_id: str = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported.")

    dest_path = UPLOADS_DIR / file.filename
    with open(dest_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # update index
    idx = read_index()
    idx[document_id] = str(dest_path.resolve())
    write_index(idx)

    return {"message": f"{file.filename} uploaded successfully.", "path": str(dest_path.resolve())}

@app.post("/ingest")
async def ingest(req: IngestReq):
    idx = read_index()
    path_str = idx.get(req.document_id)
    if not path_str or not os.path.exists(path_str):
        raise HTTPException(404, f"File for document_id {req.document_id} not found. Upload via /sanitize first.")

    path = Path(path_str)
    if path.suffix.lower() != ".pdf":
        raise HTTPException(400, "Only PDF supported in this demo.")

    chunk_gen = extract_pdf_text(path)

    chunks = []
    first_text = ""
    for i, c in enumerate(chunk_gen):
        if i == 0:
            first_text = c["text"]
        if i < 50:  # demo limit to avoid huge memory
            chunks.append(c)
        else:
            break

    meta = simple_metadata(first_text) | {"source_path": str(path.resolve())}

    return {
        "document_id": req.document_id,
        "tenant_id": req.tenant_id,
        "chunks": chunks,
        "metadata": meta
    }

@app.get("/")
async def root():
    return {"message": "FastAPI PDF Ingestor is running. Use /docs to test endpoints."}
