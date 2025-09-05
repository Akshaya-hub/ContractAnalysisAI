# Contract Analysis AI — Starter

## Quickstart
```bash
cp .env.example .env
docker compose -f deploy/docker-compose.yml up -d
python -m venv .venv && source .venv/bin/activate
pip install fastapi uvicorn[standard] httpx pydantic psycopg[binary]
# in separate terminals:
uvicorn services.security-gate.app:app --port 8001
uvicorn services.ingest-indexer.app:app --port 8002
uvicorn services.clause-extractor.app:app --port 8003
uvicorn services.risk-detector.app:app --port 8004
uvicorn services.recommender.app:app --port 8005
uvicorn services.report-maker.app:app --port 8006
uvicorn services.orchestrator.app:app --port 8000
```
Then test:
```bash
curl -s -X POST http://localhost:8000/jobs/analyze -H "Content-Type: application/json" -d '{"document_id":"doc-demo-1","tenant_id":"demo"}'
```
