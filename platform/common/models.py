from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class Span(BaseModel):
    page: Optional[int] = None
    start: Optional[int] = None
    end: Optional[int] = None

class Clause(BaseModel):
    type: str
    span: Optional[Span] = None
    text: str
    key_fields: Dict[str, Any] = {}
    summary: Optional[str] = None
    confidence: float = Field(ge=0, le=1)

class Risk(BaseModel):
    clause_type: str
    severity: str
    likelihood: str
    score: float
    issue: str
    evidence_spans: List[Span] = []
    rationale: Optional[str] = None
    confidence: float = Field(ge=0, le=1)

class Recommendation(BaseModel):
    target_clause: str
    action: str
    suggested_text: str
    priority: str
    citations: List[Dict[str, str]] = []
    diff: Optional[str] = None
