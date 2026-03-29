-- ============================================================
-- Patch workflow steps: fix template variable paths
-- trigger.object.* → trigger.properties.after.*
-- Also fix URLs: localhost → host.docker.internal
-- ============================================================

DO $BLOCK$
DECLARE
  ws TEXT := 'workspace_4qo1qwg02dcej8j8vi6yp7qsx';
  v1_id UUID := 'b1000001-0000-0000-0000-000000000001';
  v2_id UUID := 'b2000002-0000-0000-0000-000000000002';
  v3_id UUID := 'b3000003-0000-0000-0000-000000000003';
  v4_id UUID := 'b4000004-0000-0000-0000-000000000004';
  steps1 JSONB;
  steps2 JSONB;
  steps3 JSONB;
  steps4 JSONB;
BEGIN

-- WF1: Auto-folio — fix URL and trigger path
steps1 := '[{"id":"step-folio-01","name":"Generar folio TRM-YYYY-NNNN","type":"HTTP_REQUEST","valid":true,"settings":{"input":{"url":"http://host.docker.internal:4000/auto-folio","method":"POST","headers":[{"key":"Content-Type","value":"application/json"}],"body":"{\"tramiteId\": \"{{trigger.properties.after.id}}\"}","shouldFollowRedirects":true},"outputSchema":{},"errorHandlingOptions":{"retryOnFailure":{"value":false},"continueOnFailure":{"value":false}}},"nextStepIds":[]}]';

-- WF2: Auto-asignacion — fix trigger paths + records[0] → first + agente.id → agenteId
-- FIND_RECORDS devuelve .first y .all, NO .records[0]
-- El FK en _asignacion es agenteId, no agente.id
-- Nota: filter usa "and":[...] explícito. Array bare = OR en Twenty.
steps2 := '[{"id":"step-asig-01","name":"Buscar asignacion agente+ramo","type":"FIND_RECORDS","valid":true,"settings":{"input":{"objectName":"asignacion","filter":{"and":[{"asignacionActiva":{"eq":true}},{"ramo":{"eq":"{{trigger.properties.after.ramo}}"}},{"agenteId":{"eq":"{{trigger.properties.after.agenteTitularId}}"}}]},"limit":1},"outputSchema":{},"errorHandlingOptions":{"retryOnFailure":{"value":false},"continueOnFailure":{"value":true}}},"nextStepIds":["step-asig-02"]},{"id":"step-asig-02","name":"Filtrar si existe asignacion","type":"FILTER","valid":true,"settings":{"input":{"filter":"{{step-asig-01.first.id}}"},"outputSchema":{},"errorHandlingOptions":{"retryOnFailure":{"value":false},"continueOnFailure":{"value":false}}},"nextStepIds":["step-asig-03"]},{"id":"step-asig-03","name":"Asignar especialista al tramite","type":"UPDATE_RECORD","valid":true,"settings":{"input":{"objectName":"tramite","objectRecordId":"{{trigger.properties.after.id}}","objectRecord":{"especialistaAsignadoId":"{{step-asig-01.first.especialistaId}}"},"fieldsToUpdate":["especialistaAsignadoId"]},"outputSchema":{},"errorHandlingOptions":{"retryOnFailure":{"value":false},"continueOnFailure":{"value":false}}},"nextStepIds":[]}]';

-- WF3: Auto-SLA — fix URL and trigger paths
steps3 := '[{"id":"step-sla-01","name":"Calcular y guardar fechaLimiteSla","type":"HTTP_REQUEST","valid":true,"settings":{"input":{"url":"http://host.docker.internal:4000/auto-sla","method":"POST","headers":[{"key":"Content-Type","value":"application/json"}],"body":"{\"tramiteId\":\"{{trigger.properties.after.id}}\",\"ramo\":\"{{trigger.properties.after.ramo}}\",\"fechaEntrada\":\"{{trigger.properties.after.fechaEntrada}}\"}","shouldFollowRedirects":true},"outputSchema":{},"errorHandlingOptions":{"retryOnFailure":{"value":false},"continueOnFailure":{"value":false}}},"nextStepIds":[]}]';

-- WF4: Cron SLA — replace FIND_RECORDS+ITERATOR with single HTTP_REQUEST to helper
steps4 := '[{"id":"step-cron-01","name":"Buscar y marcar tramites vencidos","type":"HTTP_REQUEST","valid":true,"settings":{"input":{"url":"http://host.docker.internal:4000/mark-overdue-sla","method":"POST","headers":[{"key":"Content-Type","value":"application/json"}],"body":"{}","shouldFollowRedirects":true},"outputSchema":{},"errorHandlingOptions":{"retryOnFailure":{"value":false},"continueOnFailure":{"value":false}}},"nextStepIds":[]}]';

EXECUTE format('UPDATE %I."workflowVersion" SET steps = $1 WHERE id = $2', ws)
  USING steps1, v1_id;

EXECUTE format('UPDATE %I."workflowVersion" SET steps = $1 WHERE id = $2', ws)
  USING steps2, v2_id;

EXECUTE format('UPDATE %I."workflowVersion" SET steps = $1 WHERE id = $2', ws)
  USING steps3, v3_id;

EXECUTE format('UPDATE %I."workflowVersion" SET steps = $1 WHERE id = $2', ws)
  USING steps4, v4_id;

RAISE NOTICE 'Workflow steps patched (4 versions updated)';
END $BLOCK$;
