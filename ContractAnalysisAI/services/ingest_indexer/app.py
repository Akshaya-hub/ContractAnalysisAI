import json
import os
from io import BytesIO
from pathlib import Path
from typing import Tuple

from cryptography.fernet import Fernet
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from PyPDF2 import PdfReader

load_dotenv()


def _resolve_root() -> Path:
    override = os.getenv("PROJECT_ROOT")
    if override:
        return Path(override)
    resolved = Path(__file__).resolve()
    parents = resolved.parents
    return parents[2] if len(parents) >= 3 else parents[-1]


ROOT_DIR = _resolve_root()

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
    storage_dir_env = os.getenv("INGEST__STORAGE_DIR") or os.getenv("SECURITY_GATE__STORAGE_DIR", "storage/uploads")
    index_path_env = os.getenv("INGEST__INDEX_PATH", "storage/uploads_index.json")

    STORAGE_DIR = Path(storage_dir_env) if os.path.isabs(storage_dir_env) else ROOT_DIR / storage_dir_env
    INDEX_PATH = Path(index_path_env) if os.path.isabs(index_path_env) else ROOT_DIR / index_path_env

    FERNET_KEY = os.getenv("SECURITY_GATE__FERNET_KEY")
    FERNET = Fernet(FERNET_KEY) if FERNET_KEY else None


    def _load_index() -> dict:
        if not INDEX_PATH.exists():
            return {}
        try:
            return json.load(INDEX_PATH.open("r", encoding="utf-8"))
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="Upload index is corrupt")


    def _resolve_source(doc_id: str) -> Tuple[Path, bool]:
        index = _load_index()
        record = index.get(doc_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Document not found in index")

        if isinstance(record, str):
            path = Path(record)
            encrypted = False
        else:
            path = Path(record.get("path", ""))
            encrypted = bool(record.get("encrypted", False))

        if not path.exists():
            # fall back to legacy location if index stored relative paths
            legacy_pdf = STORAGE_DIR / f"{doc_id}.pdf"
            if legacy_pdf.exists():
                return legacy_pdf, False
            raise HTTPException(status_code=404, detail=f"Stored file missing for {doc_id}")
        return path, encrypted


    def _open_pdf(path: Path, encrypted: bool) -> PdfReader:
        if not encrypted:
            return PdfReader(str(path))
        if not FERNET:
            raise HTTPException(status_code=500, detail="Encryption key not configured")
        try:
            decrypted = FERNET.decrypt(path.read_bytes())
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to decrypt document: {exc}")
        return PdfReader(BytesIO(decrypted))

    try:
        source_path, encrypted = _resolve_source(req.document_id)
        reader = _open_pdf(source_path, encrypted)
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
