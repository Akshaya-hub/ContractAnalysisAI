import datetime as dt
import json
import logging
import mimetypes
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from cryptography.fernet import Fernet
from dotenv import load_dotenv
from fastapi import File, FastAPI, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

logger = logging.getLogger("security-gate")
logging.basicConfig(level=logging.INFO)


def _resolve_root() -> Path:
    override = os.getenv("PROJECT_ROOT")
    if override:
        return Path(override)
    resolved = Path(__file__).resolve()
    parents = resolved.parents
    return parents[2] if len(parents) >= 3 else parents[-1]


ROOT_DIR = _resolve_root()

_storage_dir = os.getenv("SECURITY_GATE__STORAGE_DIR", str(ROOT_DIR / "storage" / "uploads"))
STORAGE_DIR = Path(_storage_dir) if os.path.isabs(_storage_dir) else ROOT_DIR / _storage_dir
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

_audit_dir = os.getenv("SECURITY_GATE__AUDIT_DIR", str(ROOT_DIR / "storage" / "audit"))
AUDIT_DIR = Path(_audit_dir) if os.path.isabs(_audit_dir) else ROOT_DIR / _audit_dir
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

INDEX_PATH = ROOT_DIR / "storage" / "uploads_index.json"
INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)

FERNET_KEY = os.getenv("SECURITY_GATE__FERNET_KEY")
FERNET = Fernet(FERNET_KEY) if FERNET_KEY else None

MAX_FILE_BYTES = int(os.getenv("SECURITY_GATE__MAX_FILE_MB", "15")) * 1024 * 1024
CHUNK_SIZE = 512 * 1024

ALLOWED_FILE_TYPES: Dict[str, set[str]] = {
    "pdf": {"application/pdf"},
    "docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
        "application/octet-stream",
    },
}
allowed_origins_env = os.getenv("SECURITY_GATE__ALLOWED_ORIGINS", "*")
if allowed_origins_env.strip() == "*":
    allowed_origins = ["*"]
else:
    allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]

AUDIT_LOG_PATH = AUDIT_DIR / "security_gateway.log"
HTTP_TIMEOUT = httpx.Timeout(30.0)

INGEST_SERVICE_URL = os.getenv("SECURITY_GATE__INGEST_URL", "http://127.0.0.1:8001").rstrip("/")
CLAUSE_SERVICE_URL = os.getenv("SECURITY_GATE__CLAUSE_URL", "http://127.0.0.1:8002").rstrip("/")
RISK_SERVICE_URL = os.getenv("SECURITY_GATE__RISK_URL", "http://127.0.0.1:8003").rstrip("/")
RECOMMEND_SERVICE_URL = os.getenv("SECURITY_GATE__RECOMMEND_URL", "http://127.0.0.1:8004").rstrip("/")
CHAT_SERVICE_URL = os.getenv("SECURITY_GATE__CHAT_URL", "http://127.0.0.1:8007").rstrip("/")


class SanitizeResp(BaseModel):
    document_id: str
    filename: str
    path: str
    ok: bool = True


class IngestReq(BaseModel):
    document_id: str
    tenant_id: str


class ChatReq(BaseModel):
    document_id: str
    question: str


app = FastAPI(title="Security Gateway Service", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _audit(event: str, payload: Dict[str, Any]):
    try:
        entry = {
            "ts": dt.datetime.utcnow().isoformat() + "Z",
            "event": event,
            "payload": payload,
        }
        with AUDIT_LOG_PATH.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(entry) + "\n")
    except Exception as exc:
        logger.warning("audit log failure: %s", exc)


def _load_index() -> Dict[str, Any]:
    if INDEX_PATH.exists():
        try:
            return json.load(INDEX_PATH.open("r", encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("uploads_index.json is not valid JSON; recreating")
    return {}


def _write_index(doc_id: str, record: Dict[str, Any]):
    idx = _load_index()
    idx[doc_id] = record
    with INDEX_PATH.open("w", encoding="utf-8") as f:
        json.dump(idx, f, indent=2)


def _detect_mime(file_path: Path, fallback: Optional[str]) -> str:
    if file_path.suffix.lower() == ".pdf":
        with file_path.open("rb") as src:
            header = src.read(4)
            if header.startswith(b"%PDF"):
                return "application/pdf"
    try:
        import magic  # type: ignore

        detected = magic.from_file(str(file_path), mime=True)
        if detected:
            return detected
    except Exception:
        logger.debug("libmagic lookup failed; using mimetypes fallback")
    guess = mimetypes.guess_type(str(file_path))[0]
    return guess or (fallback or "application/octet-stream")


def _ensure_allowed(ext: str, mime_type: str):
    if ext not in ALLOWED_FILE_TYPES:
        raise HTTPException(status_code=400, detail=f"File type '.{ext}' is not permitted")
    allowed_mimes = ALLOWED_FILE_TYPES[ext]
    if mime_type in allowed_mimes:
        return
    if ext == "docx" and mime_type.startswith("application/zip"):
        return
    raise HTTPException(status_code=400, detail=f"Unsupported MIME type: {mime_type}")


@app.get("/")
def info():
    return {"service": "security-gate", "ok": True, "encrypted": bool(FERNET_KEY)}


@app.get("/health")
def health():
    return {"status": "ok", "encrypted": bool(FERNET_KEY)}


@app.post("/sanitize", response_model=SanitizeResp)
async def sanitize(request: Request, file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    ext = Path(file.filename).suffix.lower().lstrip(".")
    if not ext:
        raise HTTPException(status_code=400, detail="File extension missing")

    doc_id = str(uuid.uuid4())
    temp_path = STORAGE_DIR / f"{doc_id}.{ext}.tmp"
    total_bytes = 0

    with temp_path.open("wb") as tmp:
        while True:
            chunk = await file.read(CHUNK_SIZE)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > MAX_FILE_BYTES:
                tmp.close()
                temp_path.unlink(missing_ok=True)
                _audit("sanitize_rejected", {"reason": "file_too_large", "filename": file.filename})
                raise HTTPException(status_code=413, detail="File exceeds size limit")
            tmp.write(chunk)
    await file.close()

    if total_bytes == 0:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    mime_type = _detect_mime(temp_path, file.content_type)
    _ensure_allowed(ext, mime_type)

    if FERNET:
        final_path = STORAGE_DIR / f"{doc_id}.{ext}.enc"
        with temp_path.open("rb") as src:
            encrypted_bytes = FERNET.encrypt(src.read())
        with final_path.open("wb") as dest:
            dest.write(encrypted_bytes)
        temp_path.unlink(missing_ok=True)
    else:
        final_path = STORAGE_DIR / f"{doc_id}.{ext}"
        temp_path.rename(final_path)

    record = {
        "path": str(final_path),
        "encrypted": bool(FERNET),
        "stored_at": dt.datetime.utcnow().isoformat() + "Z",
        "original_filename": file.filename,
        "content_type": mime_type,
        "size_bytes": total_bytes,
    }
    _write_index(doc_id, record)

    client_host = request.client.host if request.client else None
    _audit(
        "sanitize_success",
        {
            "doc_id": doc_id,
            "filename": file.filename,
            "size_bytes": total_bytes,
            "client": client_host,
        },
    )
    logger.info("sanitized document %s (%s)", doc_id, file.filename)

    return SanitizeResp(document_id=doc_id, filename=file.filename, path=str(final_path), ok=True)


@app.post("/ingest")
async def proxy_ingest(request: Request, req: IngestReq):
    return await forward_request(f"{INGEST_SERVICE_URL}/ingest", req.dict(), request)


@app.get("/clauses/{doc_id}")
async def proxy_clauses(request: Request, doc_id: str):
    return await forward_request(f"{CLAUSE_SERVICE_URL}/clauses/{doc_id}", request=request)


@app.get("/risks/{doc_id}")
async def proxy_risks(request: Request, doc_id: str):
    return await forward_request(f"{RISK_SERVICE_URL}/risks/{doc_id}", request=request)


@app.get("/recommend/{doc_id}")
async def proxy_recommend(request: Request, doc_id: str):
    return await forward_request(f"{RECOMMEND_SERVICE_URL}/recommend/{doc_id}", request=request)


@app.post("/chat")
async def proxy_chat(request: Request, req: ChatReq):
    return await forward_request(f"{CHAT_SERVICE_URL}/chat", req.dict(), request)


async def forward_request(url: str, data: Optional[Dict[str, Any]] = None, request: Optional[Request] = None):
    try:
        headers: Dict[str, str] = {}
        if request:
            auth_header = request.headers.get("Authorization")
            if auth_header:
                headers["Authorization"] = auth_header
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            if data is not None:
                response = await client.post(url, json=data, headers=headers)
            else:
                response = await client.get(url, headers=headers)
            response.raise_for_status()
        return response.json()
    except httpx.RequestError as exc:
        _audit("proxy_error", {"url": url, "error": str(exc)})
        raise HTTPException(status_code=500, detail=f"Proxy error contacting {url}: {exc}")
    except httpx.HTTPStatusError as exc:
        _audit(
            "proxy_http_error",
            {
                "url": url,
                "status": exc.response.status_code,
                "body": exc.response.text[:500],
            },
        )
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
