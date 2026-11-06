-- Least-privilege server role for USIPHU's Auth0-backed PostgreSQL runtime.
-- The app connects directly to PostgreSQL and performs authorization in its
-- server-side code. It does not use Supabase Auth JWTs or auth.uid().
--
-- This role deliberately does NOT have BYPASSRLS. The policies below grant
-- access only to this dedicated server login; Supabase API roles remain denied.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'usiphu_app') THEN
    CREATE ROLE usiphu_app NOLOGIN;
  END IF;
END
$$;

GRANT CONNECT ON DATABASE postgres TO usiphu_app;
GRANT USAGE ON SCHEMA public TO usiphu_app;

DO $$
DECLARE
  table_name TEXT;
  sequence_name TEXT;
BEGIN
  FOREACH table_name IN ARRAY ARRAY[
    'flashcards',
    'generated_drafts',
    'review_states',
    'review_events',
    'question_attempts',
    'topic_progress',
    'learner_topic_progress',
    'faculty_question_reviews',
    'faculty_question_review_events',
    'faculty_reviewer_roles',
    'faculty_role_events',
    'shared_assessment_reviews',
    'shared_assessment_review_events'
  ]
  LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', table_name);
    EXECUTE format('REVOKE ALL ON TABLE public.%I FROM anon, authenticated', table_name);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.%I TO usiphu_app', table_name);
    EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', table_name || '_server_only', table_name);
    EXECUTE format(
      'CREATE POLICY %I ON public.%I FOR ALL TO usiphu_app USING (true) WITH CHECK (true)',
      table_name || '_server_only',
      table_name
    );
  END LOOP;

  -- Grant sequence access only for sequences owned by the 13 application tables.
  FOR sequence_name IN
    SELECT DISTINCT sequence_rel.relname
    FROM pg_class AS sequence_rel
    JOIN pg_depend AS dependency
      ON dependency.objid = sequence_rel.oid
    JOIN pg_class AS table_rel
      ON table_rel.oid = dependency.refobjid
    JOIN pg_namespace AS namespace
      ON namespace.oid = table_rel.relnamespace
    WHERE sequence_rel.relkind = 'S'
      AND namespace.nspname = 'public'
      AND table_rel.relname = ANY (ARRAY[
        'flashcards',
        'generated_drafts',
        'review_states',
        'review_events',
        'question_attempts',
        'topic_progress',
        'learner_topic_progress',
        'faculty_question_reviews',
        'faculty_question_review_events',
        'faculty_reviewer_roles',
        'faculty_role_events',
        'shared_assessment_reviews',
        'shared_assessment_review_events'
      ])
  LOOP
    EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE public.%I TO usiphu_app', sequence_name);
  END LOOP;
END
$$;
