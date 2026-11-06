-- Durable Source Inbox metadata. Originals and extraction JSON live in a private bucket.
CREATE TABLE IF NOT EXISTS source_documents (
  source_id TEXT PRIMARY KEY,
  sha256 TEXT NOT NULL UNIQUE,
  object_key TEXT NOT NULL UNIQUE,
  extraction_key TEXT UNIQUE,
  metadata_json TEXT NOT NULL,
  uploaded_at TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_source_documents_uploaded_at
  ON source_documents(uploaded_at DESC);
ALTER TABLE source_documents ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE source_documents FROM anon, authenticated;
CREATE POLICY source_documents_server_only ON source_documents
  FOR ALL TO public
  USING (current_user NOT IN ('anon', 'authenticated'))
  WITH CHECK (current_user NOT IN ('anon', 'authenticated'));
