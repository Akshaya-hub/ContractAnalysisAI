from fastapi import FastAPI
from pydantic import BaseModel
import httpx, uuid

app = FastAPI()

class AnalyzeReq(BaseModel):
    document_id: str
    tenant_id: str = "demo"
    profile: str = "standard_v1"
    jurisdiction: str | None = None

@app.post("/jobs/analyze")
async def analyze(req: AnalyzeReq):
    job_id = str(uuid.uuid4())
    async with httpx.AsyncClient(timeout=120) as c:
        ing = await c.post("http://localhost:8002/ingest", json=req.dict())
        clauses = await c.post("http://localhost:8003/extract", json=ing.json())
        risks = await c.post("http://localhost:8004/detect", json=clauses.json())
        recos = await c.post("http://localhost:8005/recommend", json=risks.json())
        payload = {"meta": req.dict(), **clauses.json(), **risks.json(), **recos.json()}
        report = await c.post("http://localhost:8006/render", json=payload)
    return {"job_id": job_id, "status": "completed", "report_url": report.json().get("url")}
