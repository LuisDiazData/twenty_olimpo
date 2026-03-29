-- Supabase Schema for Attachment Logging

-- 1. Create the attachments_log table
CREATE TABLE IF NOT EXISTS public.attachments_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email_id TEXT NOT NULL,
    bucket_id TEXT NOT NULL,
    total_attachments INT DEFAULT 0,
    successful_attachments INT DEFAULT 0,
    file_paths JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Optional: Add RLS policies if needed (Currently disabled for internal use)
ALTER TABLE public.attachments_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow server to insert logs" ON public.attachments_log
    FOR INSERT WITH CHECK (true);

CREATE POLICY "Allow authenticated to read logs" ON public.attachments_log
    FOR SELECT TO authenticated USING (true);

-- NOTE: Ensure a storage bucket named 'tramites-docs' exists in Supabase 
--       or update the BUCKET_NAME in the Python .env file.
