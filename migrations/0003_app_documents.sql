-- Durable JSON document pointers for approved banks and validation reports.
-- Document objects are stored privately; only server-side credentials can read them.
CREATE TABLE IF NOT EXISTS app_documents (
  document_key TEXT PRIMARY KEY,
  object_key TEXT NOT NULL UNIQUE,
  content_sha256 TEXT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE app_documents ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE app_documents FROM anon, authenticated;
CREATE POLICY app_documents_server_only ON app_documents
  FOR ALL TO public
  USING (current_user NOT IN ('anon', 'authenticated'))
  WITH CHECK (current_user NOT IN ('anon', 'authenticated'));
