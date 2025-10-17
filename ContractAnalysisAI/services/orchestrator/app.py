import asyncio
import datetime as dt
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

load_dotenv()
logger = logging.getLogger("orchestrator")
logging.basicConfig(level=logging.INFO)

ROOT_DIR = Path(__file__).resolve().parents[2]

allowed_origins_env = os.getenv("ORCH_ALLOWED_ORIGINS", "*")
if allowed_origins_env.strip() == "*":
    ALLOWED_ORIGINS = ["*"]
else:
    ALLOWED_ORIGINS = [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]

AUDIT_DIR = Path(os.getenv("ORCH_AUDIT_DIR", ROOT_DIR / "storage" / "audit"))
AUDIT_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_LOG_PATH = AUDIT_DIR / "orchestrator.log"

JWT_SECRET = os.getenv("ORCH_JWT_SECRET")
JWT_EXPIRES_MIN = int(os.getenv("ORCH_JWT_EXPIRES_MIN", "60"))
JWT_ALGORITHM = "HS256"

ADMIN_USERNAME = os.getenv("ORCH_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ORCH_PASSWORD", "change-me")

SECURITY_GATE_URL = os.getenv("ORCH_SECURITY_GATE_URL", "http://127.0.0.1:8000").rstrip("/")
INGEST_ENDPOINT = f"{SECURITY_GATE_URL}/ingest"
CLAUSE_ENDPOINT = f"{SECURITY_GATE_URL}/clauses"
RISK_ENDPOINT = f"{SECURITY_GATE_URL}/risks"
RECO_ENDPOINT = f"{SECURITY_GATE_URL}/recommend"

HTTP_TIMEOUT = httpx.Timeout(60.0)

JOBS: Dict[str, Dict[str, Any]] = {}
JOB_LOCK = asyncio.Lock()

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class OrchestrateRequest(BaseModel):
    document_id: str
    tenant_id: str = "demo"
    job_type: str = Field(default="analysis", description="Type of workflow to run")
    options: Dict[str, Any] = Field(default_factory=dict)

class OrchestrateResponse(BaseModel):
    job_id: str
    status: str

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    detail: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    events: list[Dict[str, Any]]
    created_at: str
    updated_at: str

security = HTTPBearer(auto_error=False)

app = FastAPI(title="Security Orchestrator", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _utcnow() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"

def _audit(event: str, payload: Dict[str, Any]):
    entry = {"ts": _utcnow(), "event": event, "payload": payload}
    try:
        with AUDIT_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except Exception as exc:  # non-blocking
        logger.warning("audit write failed: %s", exc)

def _create_access_token(sub: str) -> str:
    if not JWT_SECRET:
        raise HTTPException(status_code=500, detail="JWT secret not configured")
    expire = dt.datetime.utcnow() + dt.timedelta(minutes=JWT_EXPIRES_MIN)
    payload = {"sub": sub, "exp": expire, "iat": dt.datetime.utcnow(), "scope": "user"}
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token

async def _update_job(job_id: str, **fields) -> Dict[str, Any]:
    async with JOB_LOCK:
        job = JOBS[job_id]
        job.update(fields)
        job["updated_at"] = _utcnow()
        return job

async def _append_event(job_id: str, event: str, detail: Optional[Dict[str, Any]] = None):
    async with JOB_LOCK:
        job = JOBS[job_id]
        job.setdefault("events", []).append({"ts": _utcnow(), "event": event, "detail": detail or {}})
        job["updated_at"] = _utcnow()

def _get_job(job_id: str) -> Dict[str, Any]:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

def _normalize_clauses(data: Any) -> list:
    if isinstance(data, dict) and "clauses" in data:
        return data["clauses"]
    if isinstance(data, list):
        return data
    raise HTTPException(status_code=502, detail="Unexpected clause payload from agent")

def _normalize_risks(data: Any) -> list:
    if isinstance(data, dict) and "risks" in data:
        return data["risks"]
    if isinstance(data, list):
        return data
    raise HTTPException(status_code=502, detail="Unexpected risk payload from agent")

def _normalize_recos(data: Any) -> list:
    if isinstance(data, dict) and "recommendations" in data:
        return data["recommendations"]
    if isinstance(data, list):
        return data
    raise HTTPException(status_code=502, detail="Unexpected recommendation payload from agent")

async def _call_post(client: httpx.AsyncClient, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    response = await client.post(url, json=payload)
    response.raise_for_status()
    return response.json()

async def _call_get(client: httpx.AsyncClient, url: str) -> Any:
    response = await client.get(url)
    response.raise_for_status()
    return response.json()

async def _run_analysis(job_id: str, req: OrchestrateRequest, owner: str):
    await _update_job(job_id, status="running")
    _audit("job_started", {"job_id": job_id, "document_id": req.document_id, "owner": owner})

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        try:
            await _append_event(job_id, "ingest_start", {"doc": req.document_id})
            ingest_payload = {"document_id": req.document_id, "tenant_id": req.tenant_id}
            ingest_resp = await _call_post(client, INGEST_ENDPOINT, ingest_payload)
            await _append_event(job_id, "ingest_complete", {"pages": len(ingest_resp.get("chunks", []))})

            await _append_event(job_id, "clauses_start", {})
            clause_resp = await _call_get(client, f"{CLAUSE_ENDPOINT}/{req.document_id}")
            clauses = _normalize_clauses(clause_resp)
            await _append_event(job_id, "clauses_complete", {"count": len(clauses)})

            await _append_event(job_id, "risks_start", {})
            risk_resp = await _call_get(client, f"{RISK_ENDPOINT}/{req.document_id}")
            risks = _normalize_risks(risk_resp)
            await _append_event(job_id, "risks_complete", {"count": len(risks)})

            await _append_event(job_id, "recommend_start", {})
            reco_resp = await _call_get(client, f"{RECO_ENDPOINT}/{req.document_id}")
            recos = _normalize_recos(reco_resp)
            await _append_event(job_id, "recommend_complete", {"count": len(recos)})

            result = {
                "document_id": req.document_id,
                "tenant_id": req.tenant_id,
                "ingest": ingest_resp,
                "clauses": clauses,
                "risks": risks,
                "recommendations": recos,
            }

            await _update_job(job_id, status="completed", result=result, detail="workflow finished")
            _audit("job_completed", {"job_id": job_id, "owner": owner})
        except httpx.HTTPError as exc:
            message = f"Downstream agent error: {exc}"
            await _update_job(job_id, status="failed", detail=message)
            _audit("job_failed", {"job_id": job_id, "owner": owner, "error": message})
        except Exception as exc:  # unexpected
            message = f"Unexpected failure: {exc}"
            await _update_job(job_id, status="failed", detail=message)
            _audit("job_failed", {"job_id": job_id, "owner": owner, "error": message})

async def _require_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> str:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    token = credentials.credentials
    if not JWT_SECRET:
        raise HTTPException(status_code=500, detail="JWT secret not configured")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(status_code=401, detail="Invalid token: missing subject")
        return sub
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/health")
def health():
    return {"ok": True, "agents": {"ingest": INGEST_ENDPOINT, "clauses": CLAUSE_ENDPOINT, "risks": RISK_ENDPOINT}}

@app.post("/login", response_model=TokenResponse)
def login(credentials: LoginRequest):
    if credentials.username != ADMIN_USERNAME or credentials.password != ADMIN_PASSWORD:
        _audit("login_failed", {"user": credentials.username})
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = _create_access_token(credentials.username)
    _audit("login_success", {"user": credentials.username})
    return TokenResponse(access_token=token, expires_in=JWT_EXPIRES_MIN * 60)

@app.post("/orchestrate", response_model=OrchestrateResponse)
async def orchestrate(req: OrchestrateRequest, user: str = Depends(_require_user)):
    if req.job_type != "analysis":
        raise HTTPException(status_code=400, detail="Unsupported job_type")

    job_id = str(uuid.uuid4())
    job_record = {
        "job_id": job_id,
        "status": "pending",
        "detail": "queued",
        "owner": user,
        "result": None,
        "events": [],
        "created_at": _utcnow(),
        "updated_at": _utcnow(),
        "request": req.dict(),
    }
    async with JOB_LOCK:
        JOBS[job_id] = job_record

    _audit("job_queued", {"job_id": job_id, "document_id": req.document_id, "owner": user})
    asyncio.create_task(_run_analysis(job_id, req, user))
    return OrchestrateResponse(job_id=job_id, status=job_record["status"])

@app.get("/job_status/{job_id}", response_model=JobStatusResponse)
async def job_status(job_id: str, user: str = Depends(_require_user)):
    job = _get_job(job_id)
    if job.get("owner") != user:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        detail=job.get("detail"),
        result=job.get("result"),
        events=job.get("events", []),
        created_at=job["created_at"],
        updated_at=job["updated_at"],
    )
import asyncio
import datetime as dt
import json
import logging
import os
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

load_dotenv()

logger = logging.getLogger("orchestrator")
logging.basicConfig(level=logging.INFO)

ROOT_DIR = Path(__file__).resolve().parents[2]

_audit_dir = os.getenv("ORCH_AUDIT_DIR", str(ROOT_DIR / "storage" / "audit"))
AUDIT_DIR = Path(_audit_dir) if os.path.isabs(_audit_dir) else ROOT_DIR / _audit_dir
AUDIT_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_LOG_PATH = AUDIT_DIR / "orchestrator.log"

SECURITY_GATE_URL = os.getenv("ORCH_SECURITY_GATE_URL", "http://127.0.0.1:8000")
INGEST_ENDPOINT = f"{SECURITY_GATE_URL}/ingest"
CLAUSES_ENDPOINT = f"{SECURITY_GATE_URL}/clauses"
RISKS_ENDPOINT = f"{SECURITY_GATE_URL}/risks"
RECOMMEND_ENDPOINT = f"{SECURITY_GATE_URL}/recommend"

JWT_SECRET = os.getenv("ORCH_JWT_SECRET")
if not JWT_SECRET:
    logger.warning("ORCH_JWT_SECRET not set; using insecure default")
    JWT_SECRET = "change-me"
JWT_ALGORITHM = "HS256"
JWT_EXPIRES_MIN = int(os.getenv("ORCH_JWT_EXPIRES_MIN", "60"))
ORCH_USERNAME = os.getenv("ORCH_USERNAME", "admin")
ORCH_PASSWORD = os.getenv("ORCH_PASSWORD", "admin123!")
ALLOWED_JOB_TYPES = {"analysis"}
HTTP_TIMEOUT = httpx.Timeout(60.0)

origins_env = os.getenv("ORCH_ALLOWED_ORIGINS", "http://localhost:5173")
allowed_origins = [o.strip() for o in origins_env.split(",") if o.strip()] or ["*"]

security = HTTPBearer()


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class OrchestrateRequest(BaseModel):
    document_id: str = Field(..., min_length=4, pattern=r"^[a-zA-Z0-9-]+$")
    tenant_id: str = Field(default="demo", min_length=2)
    job_type: str = Field(default="analysis", pattern=r"^[a-z_]+$")
    include_recommendations: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OrchestrateResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    document_id: str
    tenant_id: str
    job_type: str
    created_at: str
    updated_at: str
    history: list[Dict[str, Any]]
    result: Optional[Dict[str, Any]] = None


app = FastAPI(title="Security Orchestrator", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

JOBS: Dict[str, Dict[str, Any]] = {}
JOBS_LOCK = asyncio.Lock()


def _now_iso() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


def _audit(event: str, payload: Dict[str, Any]):
    entry = {"ts": _now_iso(), "event": event, "payload": payload}
    try:
        with AUDIT_LOG_PATH.open("a", encoding="utf-8") as log:
            log.write(json.dumps(entry) + "\n")
    except Exception as exc:
        logger.warning("Audit log error: %s", exc)


def _create_access_token(username: str, roles: list[str]) -> str:
    now = dt.datetime.utcnow()
    payload = {
        "sub": username,
        "roles": roles,
        "iat": now,
        "exp": now + dt.timedelta(minutes=JWT_EXPIRES_MIN),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def _store_job(job_id: str, record: Dict[str, Any]):
    async with JOBS_LOCK:
        JOBS[job_id] = record


async def _update_job(job_id: str, *, status: Optional[str] = None, detail: Optional[str] = None, result: Optional[Dict[str, Any]] = None):
    async with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        if status:
            job["status"] = status
        if detail:
            job["history"].append({"ts": _now_iso(), "status": status or job["status"], "detail": detail})
        if result is not None:
            job["result"] = result
        job["updated_at"] = _now_iso()


async def _get_job(job_id: str) -> Optional[Dict[str, Any]]:
    async with JOBS_LOCK:
        job = JOBS.get(job_id)
        return deepcopy(job) if job else None


def require_role(claims: Dict[str, Any], role: str):
    roles = claims.get("roles", [])
    if role not in roles:
        raise HTTPException(status_code=403, detail="Insufficient permissions")


async def get_auth_context(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    token = credentials.credentials
    try:
        claims = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired") from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    return {"claims": claims, "token": token}


@app.get("/health")
def health():
    return {"ok": True, "jobs": len(JOBS)}


@app.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    if not (body.username == ORCH_USERNAME and body.password == ORCH_PASSWORD):
        _audit("login_failed", {"username": body.username})
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = _create_access_token(body.username, ["orchestrator"])
    _audit("login_success", {"username": body.username})
    return TokenResponse(access_token=token, expires_in=JWT_EXPIRES_MIN * 60)


@app.post("/orchestrate", response_model=OrchestrateResponse)
async def orchestrate(req: OrchestrateRequest, auth=Depends(get_auth_context)):
    claims = auth["claims"]
    require_role(claims, "orchestrator")
    if req.job_type not in ALLOWED_JOB_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported job_type")

    job_id = str(uuid.uuid4())
    record = {
        "job_id": job_id,
        "document_id": req.document_id,
        "tenant_id": req.tenant_id,
        "job_type": req.job_type,
        "status": "queued",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "history": [{"ts": _now_iso(), "status": "queued", "detail": "Job created"}],
        "result": None,
        "metadata": req.metadata,
    }
    await _store_job(job_id, record)
    _audit("job_created", {"job_id": job_id, "document_id": req.document_id, "user": claims.get("sub")})

    asyncio.create_task(_run_analysis_job(job_id, req, auth["token"]))
    return OrchestrateResponse(job_id=job_id, status="queued")


@app.get("/job_status/{job_id}", response_model=JobStatusResponse)
async def job_status(job_id: str, auth=Depends(get_auth_context)):
    claims = auth["claims"]
    require_role(claims, "orchestrator")
    job = await _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(
        job_id=job["job_id"],
        status=job["status"],
        document_id=job["document_id"],
        tenant_id=job["tenant_id"],
        job_type=job["job_type"],
        created_at=job["created_at"],
        updated_at=job["updated_at"],
        history=job["history"],
        result=job.get("result"),
    )


async def _run_analysis_job(job_id: str, req: OrchestrateRequest, bearer_token: str):
    headers = {"Authorization": f"Bearer {bearer_token}"} if bearer_token else {}
    ingest_data: Dict[str, Any] = {}
    clauses_list: list[Dict[str, Any]] = []
    risks_list: list[Dict[str, Any]] = []
    recommendations: list[Dict[str, Any]] = []

    try:
        await _update_job(job_id, status="running", detail="Starting ingest")
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            ingest_resp = await client.post(
                INGEST_ENDPOINT,
                json={"document_id": req.document_id, "tenant_id": req.tenant_id},
                headers=headers,
            )
            ingest_resp.raise_for_status()
            ingest_data = ingest_resp.json()

            await _update_job(job_id, status="running", detail="Extracting clauses")
            clauses_resp = await client.get(f"{CLAUSES_ENDPOINT}/{req.document_id}", headers=headers)
            clauses_resp.raise_for_status()
            clauses_payload = clauses_resp.json()
            if isinstance(clauses_payload, dict) and "clauses" in clauses_payload:
                clauses_list = clauses_payload["clauses"]
            elif isinstance(clauses_payload, list):
                clauses_list = clauses_payload
            else:
                clauses_list = []

            await _update_job(job_id, status="running", detail="Evaluating risks")
            risks_resp = await client.get(f"{RISKS_ENDPOINT}/{req.document_id}", headers=headers)
            risks_resp.raise_for_status()
            risks_payload = risks_resp.json()
            if isinstance(risks_payload, dict) and "risks" in risks_payload:
                risks_list = risks_payload["risks"]
            elif isinstance(risks_payload, list):
                risks_list = risks_payload

            if req.include_recommendations:
                await _update_job(job_id, status="running", detail="Generating recommendations")
                rec_resp = await client.get(f"{RECOMMEND_ENDPOINT}/{req.document_id}", headers=headers)
                rec_resp.raise_for_status()
                rec_payload = rec_resp.json()
                if isinstance(rec_payload, dict) and "recommendations" in rec_payload:
                    recommendations = rec_payload["recommendations"]
                elif isinstance(rec_payload, list):
                    recommendations = rec_payload

    except httpx.HTTPError as exc:
        message = f"Service error: {exc}"
        await _update_job(job_id, status="failed", detail=message)
        _audit("job_failed", {"job_id": job_id, "error": str(exc)})
        logger.exception("Job %s failed during HTTP call", job_id)
        return
    except Exception as exc:  # noqa: BLE001
        message = f"Unexpected error: {exc}"
        await _update_job(job_id, status="failed", detail=message)
        _audit("job_failed", {"job_id": job_id, "error": str(exc)})
        logger.exception("Job %s failed", job_id)
        return

    result = {
        "ingest": ingest_data,
        "clauses": clauses_list,
        "risks": risks_list,
        "recommendations": recommendations,
        "responsible_ai": {
            "human_review_required": True,
            "bias_mitigation": "Tenant policy thresholds applied to adjust risk levels",
            "explainability": "Each clause includes summaries and risk rationales returned by downstream agents.",
        },
    }

    await _update_job(job_id, status="completed", detail="Pipeline finished", result=result)
    _audit("job_completed", {"job_id": job_id, "document_id": req.document_id})
    logger.info("Job %s completed", job_id)
