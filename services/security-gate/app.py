from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
import uuid, os, shutil, json

UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "storage", "uploads"))
INDEX_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "storage", "uploads_index.json"))
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI()

class SanitizeResp(BaseModel):
    document_id: str
    filename: str
    path: str
    ok: bool = True

def _write_index(doc_id: str, path: str):
    idx = {}
    if os.path.exists(INDEX_PATH):
        try:
            idx = json.load(open(INDEX_PATH, "r", encoding="utf-8"))
        except Exception:
            idx = {}
    idx[doc_id] = path
    json.dump(idx, open(INDEX_PATH, "w", encoding="utf-8"))

@app.post("/sanitize", response_model=SanitizeResp)
async def sanitize(file: UploadFile = File(...)):
    # Basic checks (dev): size/type checks would go here, AV scan in prod
    if not file.filename.lower().endswith((".pdf", ".docx")):
        raise HTTPException(400, "Only PDF/DOCX supported in this demo.")

    doc_id = str(uuid.uuid4())
    ext = ".pdf" if file.filename.lower().endswith(".pdf") else ".docx"
    dest = os.path.join(UPLOAD_DIR, f"{doc_id}{ext}")
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    _write_index(doc_id, dest)
    return SanitizeResp(document_id=doc_id, filename=file.filename, path=dest, ok=True)
