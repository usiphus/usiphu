-- Defense in depth for USIPHU's Auth0-backed, server-side PostgreSQL tables.
-- The application connects directly to PostgreSQL; it does not use Supabase Auth
-- JWTs. Therefore no auth.uid()-based client policies are appropriate here.
-- Keep these tables inaccessible to Supabase API roles and permit only the
-- trusted server-side database connection (which must use a BYPASSRLS role).
DO $$
DECLARE
  table_name TEXT;
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
    EXECUTE format(
      'CREATE POLICY %I ON public.%I FOR ALL TO public USING (current_user NOT IN (''anon'', ''authenticated'')) WITH CHECK (current_user NOT IN (''anon'', ''authenticated''))',
      table_name || '_server_only',
      table_name
    );
  END LOOP;
END $$;
