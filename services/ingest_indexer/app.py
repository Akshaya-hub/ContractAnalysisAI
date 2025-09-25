from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
from pathlib import Path
from PyPDF2 import PdfReader

app = FastAPI(title="Ingest Indexer Service")

# --------- Request Model ----------
class IngestRequest(BaseModel):
    document_id: str
    tenant_id: str

# --------- Response Models ----------
class Chunk(BaseModel):
    page: int
    text: str

class Metadata(BaseModel):
    type: str = "Contract"
    parties: list[str] = []
    date: str | None = None

class IngestResponse(BaseModel):
    document_id: str
    tenant_id: str
    chunks: list[Chunk]
    metadata: Metadata

# --------- Ingest Endpoint ----------
@app.post("/ingest", response_model=IngestResponse)
def ingest_document(req: IngestRequest):
    uploads_dir = Path(__file__).resolve().parents[2] / "storage" / "uploads"
    pdf_path = uploads_dir / f"{req.document_id}.pdf"

    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {pdf_path}")

    try:
        reader = PdfReader(str(pdf_path))
        chunks = []
        for i, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            chunks.append({"page": i, "text": text.strip()})

        # Simple mock metadata
        metadata = {
            "type": "NDA",
            "parties": ["Party A", "Party B"],
            "date": "2025-01-01"
        }

        return {
            "document_id": req.document_id,
            "tenant_id": req.tenant_id,
            "chunks": chunks,
            "metadata": metadata
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingest failed: {str(e)}")

# --------- Health Check ----------
@app.get("/health")
def health():
    return {"status": "ok"}
