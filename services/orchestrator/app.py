from fastapi import FastAPI
from pydantic import BaseModel
import httpx, uuid

app = FastAPI(title="Orchestrator Service")
app = FastAPI(title="Orchestrator Service")

class AnalyzeReq(BaseModel):
    document_id: str
    tenant_id: str = "demo"
    profile: str = "standard_v1"
    jurisdiction: str | None = None

@app.post("/jobs/analyze")
async def analyze(req: AnalyzeReq):
    job_id = str(uuid.uuid4())
    async with httpx.AsyncClient(timeout=120) as c:
        # Step 1: Ingest
        ing = await c.post("http://localhost:8001/ingest", json=req.dict())
        
        # Step 2: Extract clauses
        clauses = await c.post("http://localhost:8002/extract", json=ing.json())
        
        # Step 3: Risk detection
        risks = await c.post("http://localhost:8003/detect", json=clauses.json())
        
        # Step 4: Recommendations
        recos = await c.post("http://localhost:8004/recommend", json=risks.json())
        
        # Step 5: Report rendering
        payload = {"meta": req.dict(), **clauses.json(), **risks.json(), **recos.json()}
        report = await c.post("http://localhost:8005/render", json=payload)
    
    return {"job_id": job_id, "status": "completed", "report_url": report.json().get("url")}
