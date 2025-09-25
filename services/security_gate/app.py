from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
import uuid, os, shutil, json
import httpx
from fastapi.middleware.cors import CORSMiddleware

UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "storage", "uploads"))
INDEX_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "storage", "uploads_index.json"))
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="Security Gateway Service")

# ---------- Models ----------
class SanitizeResp(BaseModel):
    document_id: str
    filename: str
    path: str
    ok: bool = True

class IngestReq(BaseModel):
    document_id: str
    tenant_id: str

# ---------- CORS ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # in prod: restrict to frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Utils ----------
def _write_index(doc_id: str, path: str):
    idx = {}
    if os.path.exists(INDEX_PATH):
        try:
            idx = json.load(open(INDEX_PATH, "r", encoding="utf-8"))
        except Exception:
            idx = {}
    idx[doc_id] = path
    json.dump(idx, open(INDEX_PATH, "w", encoding="utf-8"))

# ---------- Routes ----------
@app.post("/sanitize", response_model=SanitizeResp)
async def sanitize(file: UploadFile = File(...)):
    if not file.filename.lower().endswith((".pdf", ".docx")):
        raise HTTPException(400, "Only PDF/DOCX supported in this demo.")

    doc_id = str(uuid.uuid4())
    ext = ".pdf" if file.filename.lower().endswith(".pdf") else ".docx"
    dest = os.path.join(UPLOAD_DIR, f"{doc_id}{ext}")
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    _write_index(doc_id, dest)
    return SanitizeResp(document_id=doc_id, filename=file.filename, path=dest, ok=True)


# -------------------- PROXIES --------------------

# Ingest Service (port 8001)
@app.post("/ingest")
async def proxy_ingest(req: IngestReq):
    return await forward_request("http://127.0.0.1:8001/ingest", req.dict())


# Clause Extractor Service (port 8002)
@app.get("/clauses/{doc_id}")
async def proxy_clauses(doc_id: str):
    return await forward_request(f"http://127.0.0.1:8002/clauses/{doc_id}")


# Risk Detector Service (port 8003)
@app.get("/risks/{doc_id}")
async def proxy_risks(doc_id: str):
    return await forward_request(f"http://127.0.0.1:8003/risks/{doc_id}")


# Recommendation Agent Service (port 8004)
@app.get("/recommend/{doc_id}")
async def proxy_recommend(doc_id: str):
    return await forward_request(f"http://127.0.0.1:8004/recommend/{doc_id}")


# ---------- Forwarding Utility ----------
async def forward_request(url: str, data: dict | None = None):
    try:
        async with httpx.AsyncClient() as client:
            if data:
                r = await client.post(url, json=data)
            else:
                r = await client.get(url)
            r.raise_for_status()
        return r.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Proxy error contacting {url}: {e}")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
