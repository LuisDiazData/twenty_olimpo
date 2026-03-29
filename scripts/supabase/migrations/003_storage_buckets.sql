-- ============================================================
-- Olimpo Promotoría GNP — Supabase Storage Buckets
-- Migración 003: Crear buckets de almacenamiento
--
-- NOTA: Requiere extensión storage habilitada (por defecto en Supabase)
-- ============================================================

-- incoming-raw: emails adjuntos sin procesar desde Gmail
-- Límite: 50MB por archivo
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'incoming-raw',
  'incoming-raw',
  false,
  52428800,  -- 50 MB
  ARRAY[
    'application/pdf',
    'image/jpeg', 'image/png', 'image/tiff', 'image/webp',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'message/rfc822',
    'application/octet-stream'
  ]
)
ON CONFLICT (id) DO UPDATE SET
  file_size_limit   = EXCLUDED.file_size_limit,
  allowed_mime_types = EXCLUDED.allowed_mime_types;

-- tramite-docs: documentos finales vinculados a un Tramite en Twenty CRM
-- Organización: tramite-docs/{folio_interno}/{tipo_documento}/{filename}
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'tramite-docs',
  'tramite-docs',
  false,
  52428800,  -- 50 MB
  ARRAY[
    'application/pdf',
    'image/jpeg', 'image/png', 'image/tiff',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  ]
)
ON CONFLICT (id) DO UPDATE SET
  file_size_limit    = EXCLUDED.file_size_limit,
  allowed_mime_types = EXCLUDED.allowed_mime_types;

-- ocr-output: resultados de OCR de RunPod (texto extraído, JSON estructurado)
-- Organización: ocr-output/{attachment_id}/{result.json}
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'ocr-output',
  'ocr-output',
  false,
  10485760,  -- 10 MB
  ARRAY[
    'application/json',
    'text/plain'
  ]
)
ON CONFLICT (id) DO UPDATE SET
  file_size_limit    = EXCLUDED.file_size_limit,
  allowed_mime_types = EXCLUDED.allowed_mime_types;

-- ============================================================
-- RLS Policies para Storage
-- FastAPI usa service-role key (bypassa RLS).
-- Estas políticas son para acceso futuro desde clientes directos.
-- ============================================================

-- Política: solo service role puede leer/escribir en incoming-raw
-- (Ningún usuario frontend debe acceder a emails crudos)
CREATE POLICY "service_role_only_incoming_raw"
  ON storage.objects
  FOR ALL
  TO service_role
  USING (bucket_id = 'incoming-raw');

-- Política: service role siempre puede gestionar tramite-docs
CREATE POLICY "service_role_all_tramite_docs"
  ON storage.objects
  FOR ALL
  TO service_role
  USING (bucket_id = 'tramite-docs');

-- Política: service role gestiona ocr-output
CREATE POLICY "service_role_all_ocr_output"
  ON storage.objects
  FOR ALL
  TO service_role
  USING (bucket_id = 'ocr-output');
