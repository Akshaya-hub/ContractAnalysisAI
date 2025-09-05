\
ENV_FILE := .env
include $(ENV_FILE)
export $(shell sed 's/=.*//' $(ENV_FILE))

.PHONY: up down migrate opensearch-init kb-embed seed

up:
	docker compose -f deploy/docker-compose.yml up -d

down:
	docker compose -f deploy/docker-compose.yml down -v

migrate:
	python - <<'PY'\nimport os, psycopg\nsql=open("infra/migrations/001_init.sql").read()\nconn=psycopg.connect(os.environ.get("DATABASE_URL").replace("+psycopg",""))\nwith conn, conn.cursor() as cur: cur.execute(sql)\nprint("Migration applied.")\nPY

opensearch-init:
	curl -XPUT "http://localhost:9200/_index_template/chunks_template" -H 'Content-Type: application/json' --data-binary @infra/opensearch/chunks_template.json || true

kb-embed:
	python platform/common/embed_kb.py

seed:
	python platform/common/seed_demo.py
