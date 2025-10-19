import os
import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from PyPDF2 import PdfReader

# ---------- Setup ----------
app = FastAPI(title="Ingest Indexer Service", version="1.2.0")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ---------- Config ----------
# Shared upload directory (same as orchestrator’s)
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", r"C:\Users\shana\OneDrive\Desktop\ContractAnalysisAI\_uploads")).resolve()
os.makedirs(UPLOAD_DIR, exist_ok=True)
logging.info(f"Using UPLOAD_DIR: {UPLOAD_DIR}")

# ---------- Models ----------
class IngestRequest(BaseModel):
    document_id: str
    tenant_id: str
    sanitized_path: str | None = None

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

# ---------- Endpoint ----------
@app.post("/ingest", response_model=IngestResponse)
def ingest_document(req: IngestRequest):
    logging.info(f"Received ingest request for {req.document_id}")
    logging.info(f"Sanitized path provided: {req.sanitized_path}")

    # 1️⃣ Determine file path
    file_path = None
    if req.sanitized_path:
        possible_path = Path(req.sanitized_path).resolve()
        if possible_path.exists():
            file_path = possible_path
            logging.info(f"Found file via sanitized_path: {file_path}")
        else:
            logging.warning(f"Provided sanitized_path not found: {possible_path}")

    # 2️⃣ Fallback: look in UPLOAD_DIR
    if not file_path:
        pdf_path = UPLOAD_DIR / f"{req.document_id}_sanitized.pdf"
        docx_path = UPLOAD_DIR / f"{req.document_id}_sanitized.docx"
        if pdf_path.exists():
            file_path = pdf_path
        elif docx_path.exists():
            file_path = docx_path
        else:
            raise HTTPException(
                status_code=404,
                detail=f"File not found. Checked:\n - {pdf_path}\n - {docx_path}\n - {req.sanitized_path}"
            )

    # 3️⃣ Extract content
    chunks = []
    try:
        if file_path.suffix.lower() == ".pdf":
            reader = PdfReader(str(file_path))
            for i, page in enumerate(reader.pages, start=1):
                text = (page.extract_text() or "").strip()
                if text:
                    chunks.append({"page": i, "text": text})
        elif file_path.suffix.lower() == ".docx":
            import docx
            doc = docx.Document(str(file_path))
            full_text = "\n".join(p.text.strip() for p in doc.paragraphs if p.text.strip())
            chunks.append({"page": 1, "text": full_text})
        else:
            raise HTTPException(415, f"Unsupported file format: {file_path.suffix}")

        metadata = Metadata(
            type="NDA",
            parties=["Party A", "Party B"],
            date="2025-01-01"
        )

        logging.info(f"Ingest completed successfully for {file_path.name} ({len(chunks)} chunks)")
        return IngestResponse(
            document_id=req.document_id,
            tenant_id=req.tenant_id,
            chunks=chunks,
            metadata=metadata
        )

    except Exception as e:
        logging.exception(f"Ingest failed for {file_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Ingest failed: {e}")

# ---------- Health Check ----------
@app.get("/health")
def health():
    return {"ok": True, "uploads_dir": str(UPLOAD_DIR), "files": len(list(UPLOAD_DIR.glob('*')))}
