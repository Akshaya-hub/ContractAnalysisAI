# Contract Analysis Frontend

React + Vite UI for the ContractAnalysisAI platform. It authenticates against the orchestrator service, uploads files through the security gateway, and renders orchestration results.

## Prerequisites

- Node.js 18+ (comes with `npm`)
- Backend stack running (e.g. `docker compose -f ../deploy/docker-compose.yml up -d --build` from the repo root)

## Environment Variables

Copy `.env.example` to `.env.local` (Vite automatically loads `.env.local`).

```bash
cp .env.example .env.local
```

Adjust values as needed:

- `VITE_SECURITY_GATE_URL` – URL of the security gate (default `http://localhost:8000`)
- `VITE_ORCHESTRATOR_URL` – URL of the orchestrator API (default `http://localhost:8008`)

When you access the site from a different machine/host, point these URLs to the host where Docker is exposing the services.

## Development

```bash
npm install
npm run dev
```

The dev server runs on <http://localhost:5173>. Log in with the credentials configured in the backend `.env` (`ORCH_USERNAME` / `ORCH_PASSWORD`). Upload a PDF or DOCX file to trigger the full workflow.

## Production Build

```bash
npm run build
npm run preview   # optional: serve the built assets locally
```

The `dist/` directory can be deployed behind any static web server or bundled into a container image if needed.
