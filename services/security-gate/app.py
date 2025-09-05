from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
import uuid

app = FastAPI()

class SanitizeResp(BaseModel):
    document_id: str
    filename: str
    ok: bool = True

@app.post("/sanitize", response_model=SanitizeResp)
async def sanitize(file: UploadFile = File(...)):
    # TODO: AV, PII redaction, MIME checks
    return SanitizeResp(document_id=str(uuid.uuid4()), filename=file.filename)
