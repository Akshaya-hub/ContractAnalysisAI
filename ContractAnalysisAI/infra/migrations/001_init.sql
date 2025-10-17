CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE tenants ( id TEXT PRIMARY KEY, name TEXT NOT NULL );

CREATE TABLE documents (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  filename TEXT,
  mime TEXT,
  bytes INT,
  uploaded_at TIMESTAMPTZ DEFAULT now(),
  s3_key TEXT,
  meta JSONB
);

CREATE TABLE chunks (
  id TEXT PRIMARY KEY,
  document_id TEXT REFERENCES documents(id),
  tenant_id TEXT NOT NULL,
  page INT,
  start_char INT,
  end_char INT,
  text TEXT,
  embedding VECTOR(1536)
);

CREATE TABLE clauses (
  id TEXT PRIMARY KEY,
  document_id TEXT REFERENCES documents(id),
  tenant_id TEXT NOT NULL,
  type TEXT,
  page INT,
  start_char INT,
  end_char INT,
  text TEXT,
  key_fields JSONB,
  summary TEXT,
  confidence FLOAT
);

CREATE TABLE risks (
  id TEXT PRIMARY KEY,
  document_id TEXT REFERENCES documents(id),
  tenant_id TEXT NOT NULL,
  clause_type TEXT,
  severity TEXT,
  likelihood TEXT,
  score FLOAT,
  issue TEXT,
  evidence_spans JSONB,
  rationale TEXT,
  confidence FLOAT
);

CREATE TABLE recommendations (
  id TEXT PRIMARY KEY,
  document_id TEXT REFERENCES documents(id),
  tenant_id TEXT NOT NULL,
  target_clause TEXT,
  action TEXT,
  suggested_text TEXT,
  priority TEXT,
  citations JSONB,
  diff TEXT
);

CREATE TABLE jobs (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  document_id TEXT,
  status TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  result JSONB
);

ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE clauses ENABLE ROW LEVEL SECURITY;
ALTER TABLE risks ENABLE ROW LEVEL SECURITY;
ALTER TABLE recommendations ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY dev_all_docs ON documents FOR ALL USING (true);
CREATE POLICY dev_all_chunks ON chunks FOR ALL USING (true);
CREATE POLICY dev_all_clauses ON clauses FOR ALL USING (true);
CREATE POLICY dev_all_risks ON risks FOR ALL USING (true);
CREATE POLICY dev_all_recos ON recommendations FOR ALL USING (true);
CREATE POLICY dev_all_jobs ON jobs FOR ALL USING (true);
