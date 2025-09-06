from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
import os, io, datetime, json
from jinja2 import Environment, BaseLoader, select_autoescape
import boto3
from botocore.client import Config

from dotenv import load_dotenv; load_dotenv()



APP_VERSION = "report-1"
app = FastAPI()

@app.get("/health")
def health():
    return {"ok": True, "version": APP_VERSION}

class ReportReq(BaseModel):
    meta: Dict[str, Any]
    clauses: List[Dict[str, Any]]
    risks: List[Dict[str, Any]]
    recommendations: List[Dict[str, Any]]

HTML_TMPL = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Contract Analysis Report - {{ meta.document_id }}</title>
  <style>
    body { font-family: system-ui, Segoe UI, Arial, sans-serif; margin: 24px; }
    h1 { margin-bottom: 4px; }
    h2 { border-bottom: 1px solid #eee; padding-bottom: 4px; margin-top: 28px; }
    .muted { color: #666; font-size: 0.9em; }
    table { width: 100%; border-collapse: collapse; margin-top: 8px; }
    th, td { border: 1px solid #ddd; padding: 8px; vertical-align: top; }
    th { background: #f8f8f8; text-align: left; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 10px; background: #eef; }
    .sev-High { background: #ffe0e0; }
    .sev-Critical { background: #ffd6cc; }
    .sev-Medium { background: #fff2cc; }
    .sev-Low { background: #e7f7e7; }
    .code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; white-space: pre-wrap; }
  </style>
</head>
<body>
  <h1>Contract Analysis Report</h1>
  <div class="muted">
    Document ID: <b>{{ meta.document_id }}</b> · Tenant: <b>{{ meta.tenant_id }}</b> · Generated: {{ now }}
  </div>

  <h2>Executive Summary</h2>
  <p>Total Clauses: <b>{{ clauses|length }}</b> · Risks: <b>{{ risks|length }}</b> · Recommendations: <b>{{ recommendations|length }}</b></p>

  <h2>Clauses</h2>
  <table>
    <tr><th>Type</th><th>Page</th><th>Summary</th></tr>
    {% for c in clauses %}
      <tr>
        <td>{{ c.type }}</td>
        <td>{{ c.span.page if c.span and c.span.page is not none else "-" }}</td>
        <td>{{ c.summary or (c.text[:180] ~ ("…" if c.text|length > 180 else "")) }}</td>
      </tr>
    {% endfor %}
  </table>

  <h2>Risks</h2>
  <table>
    <tr><th>Clause</th><th>Severity</th><th>Score</th><th>Issue</th><th>Evidence</th></tr>
    {% for r in risks %}
      <tr>
        <td>{{ r.clause_type }}</td>
        <td><span class="badge sev-{{ r.severity }}">{{ r.severity }}</span></td>
        <td>{{ "%.1f"|format(r.score or 0) }}</td>
        <td>{{ r.issue }}</td>
        <td class="code">{{ (r.evidence_spans or []) | tojson }}</td>
      </tr>
    {% endfor %}
  </table>

  <h2>Recommendations</h2>
  <table>
    <tr><th>Target Clause</th><th>Action</th><th>Suggested Text</th><th>Priority</th><th>Citations</th></tr>
    {% for rec in recommendations %}
      <tr>
        <td>{{ rec.target_clause }}</td>
        <td>{{ rec.action }}</td>
        <td class="code">{{ rec.suggested_text }}</td>
        <td>{{ rec.priority }}</td>
        <td class="code">{{ (rec.citations or []) | tojson }}</td>
      </tr>
    {% endfor %}
  </table>

  <h2>Raw Data (debug)</h2>
  <details>
    <summary>Show JSON</summary>
    <pre class="code">{{ rawjson }}</pre>
  </details>
</body>
</html>
"""

def render_html(payload: Dict[str, Any]) -> bytes:
    env = Environment(
        loader=BaseLoader(),
        autoescape=select_autoescape(['html', 'xml'])
    )
    tmpl = env.from_string(HTML_TMPL)
    html = tmpl.render(
        meta=payload.get("meta", {}),
        clauses=payload.get("clauses", []),
        risks=payload.get("risks", []),
        recommendations=payload.get("recommendations", []),
        now=datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        rawjson=json.dumps(payload, indent=2)
    )
    return html.encode("utf-8")

def get_s3_client():
    endpoint = os.getenv("S3_ENDPOINT", "")
    key = os.getenv("S3_ACCESS_KEY", "")
    secret = os.getenv("S3_SECRET_KEY", "")
    region = os.getenv("S3_REGION", "us-east-1")
    if not (endpoint and key and secret):
        return None
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=key,
        aws_secret_access_key=secret,
        region_name=region,
        config=Config(signature_version="s3v4"),
    )

def ensure_bucket(client, bucket):
    try:
        client.head_bucket(Bucket=bucket)
    except Exception:
        client.create_bucket(Bucket=bucket)

@app.post("/render")
def render(req: ReportReq):
    try:
        payload = {
            "meta": req.meta,
            "clauses": req.clauses,
            "risks": req.risks,
            "recommendations": req.recommendations,
        }
        html_bytes = render_html(payload)
    except Exception as e:
        raise HTTPException(400, f"Render failed: {e}")

    # Try S3/MinIO upload first
    bucket = os.getenv("S3_BUCKET", "contracts")
    s3 = get_s3_client()
    if s3:
        key = f"reports/{req.meta.get('document_id','unknown')}-{datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.html"
        ensure_bucket(s3, bucket)
        s3.put_object(Bucket=bucket, Key=key, Body=html_bytes, ContentType="text/html; charset=utf-8")
        # presign for 7 days (604800 seconds)
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=604800
        )
        return {"url": url}

    # Fallback: write to local file and return a file URL
    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "storage", "reports"))
    os.makedirs(out_dir, exist_ok=True)
    fname = f"{req.meta.get('document_id','unknown')}.html"
    fpath = os.path.join(out_dir, fname)
    with open(fpath, "wb") as f:
        f.write(html_bytes)
    return {"url": f"file://{fpath}"}
