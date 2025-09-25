# services/security-gate/app.py

import os
import uuid
import hashlib
import logging
from typing import Dict, Optional

from pathlib import Path
import sys

# ------------------------------------------------------------------------
# Ensure the repo root (…/ContractAnalysisAI) is importable BEFORE imports
# ------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, UploadFile, File, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# ------------------------------------------------------------------------
# Import your shared model (after sys.path fix)
# ------------------------------------------------------------------------
from app_platform.common.models import SecurityScanReport  # make sure this exists

# ------------------------------------------------------------------------
# Optional MIME sniffer (python-magic is often missing on Windows)
# ------------------------------------------------------------------------
try:
    import magic  # type: ignore
except Exception:
    magic = None

# ------------------------------------------------------------------------
# PDF engine: prefer pikepdf; fallback to pypdf if not available
# ------------------------------------------------------------------------
HAVE_PIKEPDF = False
try:
    import pikepdf  # type: ignore
    HAVE_PIKEPDF = True
except Exception:
    try:
        from pypdf import PdfReader, PdfWriter  # type: ignore
    except Exception:
        PdfReader = None
        PdfWriter = None

BUILD_TAG = "sgate-2025-09-26c"

# Load environment from repo root .env (if present)
load_dotenv(ROOT / ".env")

app = FastAPI(title="Security & Sanitization Gate", version="0.1.3")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./_uploads")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "15"))
SERVICE_SECRET = os.getenv("SERVICE_SECRET", "dev-secret")

os.makedirs(UPLOAD_DIR, exist_ok=True)
logging.basicConfig(level=logging.INFO)


# ------------------ helpers ------------------

def _auth(secret: Optional[str]) -> None:
    if (secret or "") != SERVICE_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def _basic_pdf_checks(raw: bytes) -> Dict[str, bool]:
    """Lightweight, Windows-safe PDF detection."""
    is_pdf_header = raw[:5] == b"%PDF-"
    is_pdf_mime = False
    if magic is not None:
        try:
            mime = magic.from_buffer(raw, mime=True) or ""
            is_pdf_mime = "pdf" in mime
        except Exception:
            is_pdf_mime = False
    # If python-magic is missing, trust the header sniffer.
    return {
        "is_pdf_header": bool(is_pdf_header),
        "is_pdf_mime": bool(is_pdf_mime or is_pdf_header),
    }


def _get_pdf_info(src_path: str) -> tuple[bool, int]:
    """
    Returns (is_encrypted, pages) using available PDF engine.
    """
    if HAVE_PIKEPDF:
        try:
            with pikepdf.open(src_path) as pdf:
                return (pdf.is_encrypted, len(pdf.pages))
        except pikepdf.PasswordError:
            return (True, 0)
    else:
        if PdfReader is None:
            raise HTTPException(
                status_code=500,
                detail="No PDF engine available. Install pikepdf or pypdf."
            )
        reader = PdfReader(src_path, strict=False)
        if getattr(reader, "is_encrypted", False):
            return (True, 0)
        try:
            pages = len(reader.pages)
        except Exception:
            pages = 0
        return (False, pages)


def _sanitize_pdf(src_path: str, dst_path: str) -> Dict[str, int] | int:
    """
    Sanitize using pikepdf when available; otherwise do a conservative pypdf pass.
    Returns a dict of counters, or -1 if encrypted/unhandled.
    """
    removed = {
        "javascript": 0,
        "open_actions": 0,
        "embedded_files": 0,
        "annotations_removed": 0,
        "names_javascript": 0,
        "metadata_cleared": 0,
    }

    if HAVE_PIKEPDF:
        try:
            with pikepdf.open(src_path, allow_overwriting_input=True) as pdf:
                if pdf.is_encrypted:
                    return -1

                # Clear Document Info (indirect)
                try:
                    pdf.trailer["/Info"] = pdf.make_indirect(pikepdf.Dictionary())
                    removed["metadata_cleared"] += 1
                except Exception as e:
                    logging.warning("docinfo wipe failed: %s", e)

                # Access catalog via trailer
                try:
                    root = pdf.trailer.get("/Root")
                    pdf.trailer["/Info"] = pdf.make_indirect(pikepdf.Dictionary())
                except Exception:
                    root = None

                # Remove XMP metadata stream from catalog
                try:
                    if root is not None and "/Metadata" in root:
                        del root["/Metadata"]
                        removed["metadata_cleared"] += 1
                except Exception as e:
                    logging.warning("XMP removal failed: %s", e)

                # Remove auto actions from catalog
                if root is not None:
                    for key in ("/OpenAction", "/AA"):
                        try:
                            if key in root:
                                del root[key]
                                removed["open_actions"] += 1
                        except Exception:
                            pass

                    # Remove JS & EmbeddedFiles from /Names
                    try:
                        if "/Names" in root:
                            names = root["/Names"]
                            if "/JavaScript" in names:
                                del names["/JavaScript"]
                                removed["names_javascript"] += 1
                            if "/EmbeddedFiles" in names:
                                del names["/EmbeddedFiles"]
                                removed["embedded_files"] += 1
                    except Exception:
                        pass

                # Scrub page annotations & JS
                JS_KEYS = ("/JS", "/JavaScript")
                BAD_SUBTYPES = {
                    pikepdf.Name(n) for n in ["/FileAttachment", "/RichMedia", "/Movie", "/Sound"]
                }
                for page in pdf.pages:
                    if "/Annots" not in page:
                        continue
                    annots = page["/Annots"]
                    try:
                        new_annots = pikepdf.Array()
                        for a in annots:
                            obj = a.get_object()
                            drop = False
                            # JS in actions
                            if "/A" in obj:
                                action = obj["/A"]
                                if any(k in action for k in JS_KEYS):
                                    removed["javascript"] += 1
                                    drop = True
                            # explicit JS entries
                            if any(k in obj for k in JS_KEYS):
                                removed["javascript"] += 1
                                drop = True
                            # attachment/media
                            if obj.get("/Subtype") in BAD_SUBTYPES:
                                removed["annotations_removed"] += 1
                                drop = True
                            if not drop:
                                new_annots.append(obj)
                        page["/Annots"] = new_annots
                    except Exception:
                        # if anything odd, drop all annots on that page (safe default)
                        page["/Annots"] = pikepdf.Array()
                        removed["annotations_removed"] += 1

                pdf.save(dst_path)
                return removed

        except pikepdf.PasswordError:
            return -1

    # -------- pypdf fallback (coarse sanitation) --------
    if PdfReader is None or PdfWriter is None:
        raise HTTPException(
            status_code=500,
            detail="No PDF engine available. Install pikepdf or pypdf."
        )

    reader = PdfReader(src_path, strict=False)
    if getattr(reader, "is_encrypted", False):
        return -1

    writer = PdfWriter()
    # Try removing metadata and annotations in a basic way
    try:
        writer.add_metadata({})  # clear Info dict
        removed["metadata_cleared"] += 1
    except Exception:
        pass

    try:
        root = reader.trailer.get("/Root")
        if root and "/Metadata" in root:
            # Clearing XMP is non-trivial in pypdf; we skip deep manipulation
            removed["metadata_cleared"] += 0  # no-op marker
    except Exception:
        pass

    try:
        for page in reader.pages:
            # Drop annotations wholesale if present
            if "/Annots" in page:
                try:
                    del page["/Annots"]
                    removed["annotations_removed"] += 1
                except Exception:
                    # fallback to empty
                    page["/Annots"] = []
                    removed["annotations_removed"] += 1
            writer.add_page(page)
        with open(dst_path, "wb") as fout:
            writer.write(fout)
    except Exception as e:
        logging.exception("pypdf fallback failed: %s", e)
        return -1

    # We cannot robustly strip JS/OpenAction/Names via pypdf without deep edits,
    # so we only count annotations/metadata in fallback mode.
    return removed


# ------------------ routes ------------------

@app.get("/")
def root():
    return {"service": "security-gate", "ok": True, "build": BUILD_TAG}


@app.get("/health")
def health():
    return {"ok": True, "build": BUILD_TAG}


@app.post("/v1/security/scan-upload", response_model=SecurityScanReport)
async def scan_upload(
    file: UploadFile = File(...),
    x_secret_query: Optional[str] = Query(default=None, alias="x_secret"),
    x_secret_header: Optional[str] = Header(default=None, alias="x-secret"),
):
    """
    Accept a PDF, sanitize it, and return a report.
    Auth: pass x_secret=... as query or x-secret: ... as header.
    """
    # ---- auth
    _auth(x_secret_header or x_secret_query)

    raw = await file.read()
    size_bytes = len(raw)
    if size_bytes == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if size_bytes > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File too large (> {MAX_UPLOAD_MB} MB)")

    # ---- checks
    checks = _basic_pdf_checks(raw)
    if not (checks["is_pdf_header"] and checks["is_pdf_mime"]):
        raise HTTPException(status_code=415, detail="Only PDF files are allowed")

    # ---- write temp source
    file_id = str(uuid.uuid4())
    src_path = os.path.join(UPLOAD_DIR, f"{file_id}_source.pdf")
    dst_path = os.path.join(UPLOAD_DIR, f"{file_id}_sanitized.pdf")
    with open(src_path, "wb") as f:
        f.write(raw)

    # ---- quick open for encryption + pages
    is_encrypted, pages = _get_pdf_info(src_path)
    if is_encrypted:
        try:
            os.remove(src_path)
        finally:
            ...
        raise HTTPException(status_code=400, detail="Password-protected/encrypted PDFs are not allowed")

    # ---- sanitize
    removed = _sanitize_pdf(src_path, dst_path)
    if removed == -1:
        try:
            os.remove(src_path)
        finally:
            ...
        raise HTTPException(status_code=400, detail="Could not sanitize (possibly encrypted)")

    # ---- hash sanitized bytes
    with open(dst_path, "rb") as f:
        sha256 = _sha256_bytes(f.read())

    logging.info("sanitized file_id=%s sha256=%s size=%s", file_id, sha256[:10] + "...", size_bytes)

    # ---- build response
    notes = "Sanitization complete (pikepdf)" if HAVE_PIKEPDF else "Sanitization complete (pypdf fallback)"
    report = SecurityScanReport(
        file_id=file_id,
        sha256=sha256,
        size_bytes=size_bytes,
        is_pdf=True,
        is_encrypted=False,
        pages=pages,
        removed=removed,  # type: ignore[arg-type]
        notes=notes,
        sanitized_path=str(Path(dst_path).resolve()),
    )

    # remove original
    try:
        os.remove(src_path)
    except Exception:
        pass

    return report
