# Contract Analysis AI — Starter

## Quickstart

1. Copy the sample environment file and populate the secrets:

	```bash
	cp .env.example .env
	```

	- Generate a Fernet key for the security gate if encryption is enabled:

	  ```bash
	  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
	  ```
	- When running with Docker Compose, point any `http://localhost` service URLs (e.g. `S3_ENDPOINT`, `DATABASE_URL`) to the container names such as `http://minio:9000`.

2. Build and start the infrastructure and microservices:

	```bash
	docker compose -f deploy/docker-compose.yml up -d --build
	```

	This brings up Postgres, OpenSearch, MinIO, NATS, Keycloak, and all FastAPI services (security-gate on `http://localhost:8000`, orchestrator on `http://localhost:8008`, etc.).

3. Install and run the frontend (in a separate terminal):

	```bash
	cd contract-frontend
	npm install
	npm run dev
	```

4. Log in via the frontend using the credentials from `.env` (`ORCH_USERNAME` / `ORCH_PASSWORD`), upload a contract, and monitor orchestration progress.
