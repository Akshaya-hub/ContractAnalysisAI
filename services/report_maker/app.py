from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any

app = FastAPI()

class ReportReq(BaseModel):
    meta: Dict[str, Any]
    clauses: list
    risks: list
    recommendations: list

@app.post("/render")
async def render(req: ReportReq):
    # In real system: render HTML/PDF and upload to S3; return signed URL
    # For demo, return a pretend URL:
    return {"url": "https://example.com/report/demo-report.html"}
