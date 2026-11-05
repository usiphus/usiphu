-- Durable JSON banks and report snapshots; objects are stored in a private bucket.
CREATE TABLE IF NOT EXISTS app_documents (
  document_key TEXT PRIMARY KEY,
  object_key TEXT NOT NULL UNIQUE,
  content_sha256 TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_app_documents_updated_at
  ON app_documents(updated_at DESC);
ALTER TABLE app_documents ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE app_documents FROM anon, authenticated;
CREATE POLICY app_documents_server_only ON app_documents
  FOR ALL TO public
  USING (current_user NOT IN ('anon', 'authenticated'))
  WITH CHECK (current_user NOT IN ('anon', 'authenticated'));
