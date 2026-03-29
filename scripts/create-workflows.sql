-- ============================================================
-- Crear 4 workflows para la promotoría de seguros
-- ============================================================

DO $BLOCK$
DECLARE
  ws TEXT := 'workspace_4qo1qwg02dcej8j8vi6yp7qsx';
  wf1_id UUID := 'a1000001-0000-0000-0000-000000000001';
  wf2_id UUID := 'a2000002-0000-0000-0000-000000000002';
  wf3_id UUID := 'a3000003-0000-0000-0000-000000000003';
  wf4_id UUID := 'a4000004-0000-0000-0000-000000000004';
  v1_id  UUID := 'b1000001-0000-0000-0000-000000000001';
  v2_id  UUID := 'b2000002-0000-0000-0000-000000000002';
  v3_id  UUID := 'b3000003-0000-0000-0000-000000000003';
  v4_id  UUID := 'b4000004-0000-0000-0000-000000000004';
  at1_id UUID := 'c1000001-0000-0000-0000-000000000001';
  at2_id UUID := 'c2000002-0000-0000-0000-000000000002';
  at3_id UUID := 'c3000003-0000-0000-0000-000000000003';
  at4_id UUID := 'c4000004-0000-0000-0000-000000000004';
  trig1 JSONB;
  trig2 JSONB;
  trig3 JSONB;
  trig4 JSONB;
  steps1 JSONB;
  steps2 JSONB;
  steps3 JSONB;
  steps4 JSONB;
BEGIN

-- ---- Triggers ----
trig1 := '{"type":"DATABASE_EVENT","name":"Tramite creado","settings":{"eventName":"tramite.created","objectType":"tramite","outputSchema":{}},"nextStepIds":["step-folio-01"]}';
trig2 := '{"type":"DATABASE_EVENT","name":"Tramite creado sin especialista","settings":{"eventName":"tramite.created","objectType":"tramite","outputSchema":{}},"nextStepIds":["step-asig-01"]}';
trig3 := '{"type":"DATABASE_EVENT","name":"Tramite creado","settings":{"eventName":"tramite.created","objectType":"tramite","outputSchema":{}},"nextStepIds":["step-sla-01"]}';
trig4 := '{"type":"CRON","name":"Cada dia a las 8:00 AM","settings":{"type":"CUSTOM","pattern":"0 8 * * *","outputSchema":{}},"nextStepIds":["step-cron-01"]}';

-- ---- Steps WF1: Auto-folio ----
steps1 := '[{"id":"step-folio-01","name":"Generar folio TRM-YYYY-NNNN","type":"HTTP_REQUEST","valid":true,"settings":{"input":{"url":"http://host.docker.internal:4000/auto-folio","method":"POST","headers":[{"key":"Content-Type","value":"application/json"}],"body":"{\"tramiteId\": \"{{trigger.properties.after.id}}\"}","shouldFollowRedirects":true},"outputSchema":{},"errorHandlingOptions":{"retryOnFailure":{"value":false},"continueOnFailure":{"value":false}}},"nextStepIds":[]}]';

-- ---- Steps WF2: Auto-asignacion ----
steps2 := '[{"id":"step-asig-01","name":"Buscar asignacion agente+ramo","type":"FIND_RECORDS","valid":true,"settings":{"input":{"objectName":"asignacion","filter":{"gqlOperationFilter":[{"asignacionActiva":{"eq":true}},{"ramo":{"eq":"{{trigger.properties.after.ramo}}"}},{"agente":{"id":{"eq":"{{trigger.properties.after.agenteTitularId}}"}}}]},"limit":1},"outputSchema":{},"errorHandlingOptions":{"retryOnFailure":{"value":false},"continueOnFailure":{"value":true}}},"nextStepIds":["step-asig-02"]},{"id":"step-asig-02","name":"Filtrar si existe asignacion","type":"FILTER","valid":true,"settings":{"input":{"filter":"{{step-asig-01.records[0].id}}"},"outputSchema":{},"errorHandlingOptions":{"retryOnFailure":{"value":false},"continueOnFailure":{"value":false}}},"nextStepIds":["step-asig-03"]},{"id":"step-asig-03","name":"Asignar especialista al tramite","type":"UPDATE_RECORD","valid":true,"settings":{"input":{"objectName":"tramite","objectRecordId":"{{trigger.properties.after.id}}","objectRecord":{"especialistaAsignadoId":"{{step-asig-01.records[0].especialistaId}}"},"fieldsToUpdate":["especialistaAsignadoId"]},"outputSchema":{},"errorHandlingOptions":{"retryOnFailure":{"value":false},"continueOnFailure":{"value":false}}},"nextStepIds":[]}]';

-- ---- Steps WF3: Auto-SLA ----
steps3 := '[{"id":"step-sla-01","name":"Calcular y guardar fechaLimiteSla","type":"HTTP_REQUEST","valid":true,"settings":{"input":{"url":"http://host.docker.internal:4000/auto-sla","method":"POST","headers":[{"key":"Content-Type","value":"application/json"}],"body":"{\"tramiteId\":\"{{trigger.properties.after.id}}\",\"ramo\":\"{{trigger.properties.after.ramo}}\",\"fechaEntrada\":\"{{trigger.properties.after.fechaEntrada}}\"}","shouldFollowRedirects":true},"outputSchema":{},"errorHandlingOptions":{"retryOnFailure":{"value":false},"continueOnFailure":{"value":false}}},"nextStepIds":[]}]';

-- ---- Steps WF4: Cron fuera de SLA ----
-- Nota: el step-cron-01 delega a helper server para filtrar correctamente con la fecha actual
steps4 := '[{"id":"step-cron-01","name":"Buscar y marcar tramites vencidos","type":"HTTP_REQUEST","valid":true,"settings":{"input":{"url":"http://host.docker.internal:4000/mark-overdue-sla","method":"POST","headers":[{"key":"Content-Type","value":"application/json"}],"body":"{}","shouldFollowRedirects":true},"outputSchema":{},"errorHandlingOptions":{"retryOnFailure":{"value":false},"continueOnFailure":{"value":false}}},"nextStepIds":[]}]';

-- ============================================================
-- Insertar workflows
-- ============================================================
EXECUTE format(
  'INSERT INTO %I.workflow (id, name, "lastPublishedVersionId", statuses, position, "createdBySource", "createdByName")
   VALUES ($1,$2,$3,ARRAY[''ACTIVE''::%I.workflow_statuses_enum],$5,$6,$7) ON CONFLICT (id) DO NOTHING', ws, ws)
  USING wf1_id, 'Auto-folio: TRM-YYYY-NNNN', v1_id::text, NULL, 10, 'API', 'System';

EXECUTE format(
  'INSERT INTO %I.workflow (id, name, "lastPublishedVersionId", statuses, position, "createdBySource", "createdByName")
   VALUES ($1,$2,$3,ARRAY[''ACTIVE''::%I.workflow_statuses_enum],$5,$6,$7) ON CONFLICT (id) DO NOTHING', ws, ws)
  USING wf2_id, 'Auto-asignacion de especialista', v2_id::text, NULL, 11, 'API', 'System';

EXECUTE format(
  'INSERT INTO %I.workflow (id, name, "lastPublishedVersionId", statuses, position, "createdBySource", "createdByName")
   VALUES ($1,$2,$3,ARRAY[''ACTIVE''::%I.workflow_statuses_enum],$5,$6,$7) ON CONFLICT (id) DO NOTHING', ws, ws)
  USING wf3_id, 'Auto-fecha limite SLA', v3_id::text, NULL, 12, 'API', 'System';

EXECUTE format(
  'INSERT INTO %I.workflow (id, name, "lastPublishedVersionId", statuses, position, "createdBySource", "createdByName")
   VALUES ($1,$2,$3,ARRAY[''ACTIVE''::%I.workflow_statuses_enum],$5,$6,$7) ON CONFLICT (id) DO NOTHING', ws, ws)
  USING wf4_id, 'Cron diario: marcar fuera de SLA', v4_id::text, NULL, 13, 'API', 'System';

-- ============================================================
-- Insertar versiones
-- ============================================================
EXECUTE format(
  'INSERT INTO %I."workflowVersion" (id, "workflowId", status, name, trigger, steps, position, "createdBySource", "createdByName")
   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) ON CONFLICT (id) DO NOTHING', ws)
  USING v1_id, wf1_id,
    'ACTIVE'::"workspace_4qo1qwg02dcej8j8vi6yp7qsx"."workflowVersion_status_enum",
    'v1', trig1, steps1, 1, 'API', 'System';

EXECUTE format(
  'INSERT INTO %I."workflowVersion" (id, "workflowId", status, name, trigger, steps, position, "createdBySource", "createdByName")
   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) ON CONFLICT (id) DO NOTHING', ws)
  USING v2_id, wf2_id,
    'ACTIVE'::"workspace_4qo1qwg02dcej8j8vi6yp7qsx"."workflowVersion_status_enum",
    'v1', trig2, steps2, 1, 'API', 'System';

EXECUTE format(
  'INSERT INTO %I."workflowVersion" (id, "workflowId", status, name, trigger, steps, position, "createdBySource", "createdByName")
   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) ON CONFLICT (id) DO NOTHING', ws)
  USING v3_id, wf3_id,
    'ACTIVE'::"workspace_4qo1qwg02dcej8j8vi6yp7qsx"."workflowVersion_status_enum",
    'v1', trig3, steps3, 1, 'API', 'System';

EXECUTE format(
  'INSERT INTO %I."workflowVersion" (id, "workflowId", status, name, trigger, steps, position, "createdBySource", "createdByName")
   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) ON CONFLICT (id) DO NOTHING', ws)
  USING v4_id, wf4_id,
    'ACTIVE'::"workspace_4qo1qwg02dcej8j8vi6yp7qsx"."workflowVersion_status_enum",
    'v1', trig4, steps4, 1, 'API', 'System';

-- ============================================================
-- Insertar automated triggers (activan la escucha de eventos)
-- ============================================================
EXECUTE format(
  'INSERT INTO %I."workflowAutomatedTrigger" (id, type, settings, "workflowId", position, "createdBySource", "createdByName")
   VALUES ($1,$2,$3,$4,$5,$6,$7) ON CONFLICT (id) DO NOTHING', ws)
  USING at1_id,
    'DATABASE_EVENT'::"workspace_4qo1qwg02dcej8j8vi6yp7qsx"."workflowAutomatedTrigger_type_enum",
    '{"eventName":"tramite.created","objectType":"tramite"}'::jsonb,
    wf1_id, 1, 'API', 'System';

EXECUTE format(
  'INSERT INTO %I."workflowAutomatedTrigger" (id, type, settings, "workflowId", position, "createdBySource", "createdByName")
   VALUES ($1,$2,$3,$4,$5,$6,$7) ON CONFLICT (id) DO NOTHING', ws)
  USING at2_id,
    'DATABASE_EVENT'::"workspace_4qo1qwg02dcej8j8vi6yp7qsx"."workflowAutomatedTrigger_type_enum",
    '{"eventName":"tramite.created","objectType":"tramite"}'::jsonb,
    wf2_id, 2, 'API', 'System';

EXECUTE format(
  'INSERT INTO %I."workflowAutomatedTrigger" (id, type, settings, "workflowId", position, "createdBySource", "createdByName")
   VALUES ($1,$2,$3,$4,$5,$6,$7) ON CONFLICT (id) DO NOTHING', ws)
  USING at3_id,
    'DATABASE_EVENT'::"workspace_4qo1qwg02dcej8j8vi6yp7qsx"."workflowAutomatedTrigger_type_enum",
    '{"eventName":"tramite.created","objectType":"tramite"}'::jsonb,
    wf3_id, 3, 'API', 'System';

EXECUTE format(
  'INSERT INTO %I."workflowAutomatedTrigger" (id, type, settings, "workflowId", position, "createdBySource", "createdByName")
   VALUES ($1,$2,$3,$4,$5,$6,$7) ON CONFLICT (id) DO NOTHING', ws)
  USING at4_id,
    'CRON'::"workspace_4qo1qwg02dcej8j8vi6yp7qsx"."workflowAutomatedTrigger_type_enum",
    '{"type":"CUSTOM","pattern":"0 8 * * *"}'::jsonb,
    wf4_id, 4, 'API', 'System';

RAISE NOTICE '4 workflows creados correctamente';
END $BLOCK$;
