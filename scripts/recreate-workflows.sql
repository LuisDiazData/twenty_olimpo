-- Elimina workflows con UUIDs inválidos (dígito de versión 0) y los recrea con gen_random_uuid()
-- createdBySource y createdByName usan sus defaults (MANUAL / System)
DO $BLOCK$
DECLARE
  ws TEXT := 'workspace_4qo1qwg02dcej8j8vi6yp7qsx';

  old_wf1 UUID := 'a1000001-0000-0000-0000-000000000001';
  old_wf2 UUID := 'a2000002-0000-0000-0000-000000000002';
  old_wf3 UUID := 'a3000003-0000-0000-0000-000000000003';
  old_wf4 UUID := 'a4000004-0000-0000-0000-000000000004';
  old_v1  UUID := 'b1000001-0000-0000-0000-000000000001';
  old_v2  UUID := 'b2000002-0000-0000-0000-000000000002';
  old_v3  UUID := 'b3000003-0000-0000-0000-000000000003';
  old_v4  UUID := 'b4000004-0000-0000-0000-000000000004';
  old_at1 UUID := 'c1000001-0000-0000-0000-000000000001';
  old_at2 UUID := 'c2000002-0000-0000-0000-000000000002';
  old_at3 UUID := 'c3000003-0000-0000-0000-000000000003';
  old_at4 UUID := 'c4000004-0000-0000-0000-000000000004';

  wf1_id UUID := gen_random_uuid();
  wf2_id UUID := gen_random_uuid();
  wf3_id UUID := gen_random_uuid();
  wf4_id UUID := gen_random_uuid();
  v1_id  UUID := gen_random_uuid();
  v2_id  UUID := gen_random_uuid();
  v3_id  UUID := gen_random_uuid();
  v4_id  UUID := gen_random_uuid();
  at1_id UUID := gen_random_uuid();
  at2_id UUID := gen_random_uuid();
  at3_id UUID := gen_random_uuid();
  at4_id UUID := gen_random_uuid();

  trig1  JSONB; trig2  JSONB; trig3  JSONB; trig4  JSONB;
  steps1 JSONB; steps2 JSONB; steps3 JSONB; steps4 JSONB;
  wf_pos FLOAT;
BEGIN

  EXECUTE format('SELECT position FROM %I.workflow WHERE id=$1', ws) INTO wf_pos USING old_wf1;

  EXECUTE format('SELECT trigger FROM %I."workflowVersion" WHERE id=$1', ws) INTO trig1  USING old_v1;
  EXECUTE format('SELECT steps   FROM %I."workflowVersion" WHERE id=$1', ws) INTO steps1 USING old_v1;
  EXECUTE format('SELECT trigger FROM %I."workflowVersion" WHERE id=$1', ws) INTO trig2  USING old_v2;
  EXECUTE format('SELECT steps   FROM %I."workflowVersion" WHERE id=$1', ws) INTO steps2 USING old_v2;
  EXECUTE format('SELECT trigger FROM %I."workflowVersion" WHERE id=$1', ws) INTO trig3  USING old_v3;
  EXECUTE format('SELECT steps   FROM %I."workflowVersion" WHERE id=$1', ws) INTO steps3 USING old_v3;
  EXECUTE format('SELECT trigger FROM %I."workflowVersion" WHERE id=$1', ws) INTO trig4  USING old_v4;
  EXECUTE format('SELECT steps   FROM %I."workflowVersion" WHERE id=$1', ws) INTO steps4 USING old_v4;

  -- Borrar registros viejos
  EXECUTE format('DELETE FROM %I."workflowAutomatedTrigger" WHERE id IN ($1,$2,$3,$4)', ws)
    USING old_at1, old_at2, old_at3, old_at4;
  EXECUTE format('DELETE FROM %I."workflowRun" WHERE "workflowVersionId" IN ($1,$2,$3,$4)', ws)
    USING old_v1, old_v2, old_v3, old_v4;
  EXECUTE format('DELETE FROM %I."workflowVersion" WHERE id IN ($1,$2,$3,$4)', ws)
    USING old_v1, old_v2, old_v3, old_v4;
  EXECUTE format('DELETE FROM %I.workflow WHERE id IN ($1,$2,$3,$4)', ws)
    USING old_wf1, old_wf2, old_wf3, old_wf4;

  -- Insertar workflows (sin createdBySource/Name — usan defaults MANUAL/System)
  EXECUTE format(
    'INSERT INTO %I.workflow (id,name,"lastPublishedVersionId",statuses,position) VALUES ($1,$2,$3::text,ARRAY[''ACTIVE''::%I.workflow_statuses_enum],$5)',
    ws, ws) USING wf1_id, 'Auto-folio: TRM-YYYY-NNNN',        v1_id, NULL, wf_pos;
  EXECUTE format(
    'INSERT INTO %I.workflow (id,name,"lastPublishedVersionId",statuses,position) VALUES ($1,$2,$3::text,ARRAY[''ACTIVE''::%I.workflow_statuses_enum],$5)',
    ws, ws) USING wf2_id, 'Auto-asignacion de especialista',   v2_id, NULL, wf_pos+1;
  EXECUTE format(
    'INSERT INTO %I.workflow (id,name,"lastPublishedVersionId",statuses,position) VALUES ($1,$2,$3::text,ARRAY[''ACTIVE''::%I.workflow_statuses_enum],$5)',
    ws, ws) USING wf3_id, 'Auto-fecha limite SLA',             v3_id, NULL, wf_pos+2;
  EXECUTE format(
    'INSERT INTO %I.workflow (id,name,"lastPublishedVersionId",statuses,position) VALUES ($1,$2,$3::text,ARRAY[''ACTIVE''::%I.workflow_statuses_enum],$5)',
    ws, ws) USING wf4_id, 'Cron diario: marcar fuera de SLA', v4_id, NULL, wf_pos+3;

  -- Insertar versiones (sin createdBySource/Name — usan defaults)
  EXECUTE format(
    'INSERT INTO %I."workflowVersion" (id,"workflowId",status,name,trigger,steps,position) VALUES ($1,$2,$3,$4,$5,$6,$7)',
    ws) USING v1_id, wf1_id, 'ACTIVE'::"workspace_4qo1qwg02dcej8j8vi6yp7qsx"."workflowVersion_status_enum", 'v1', trig1, steps1, 1;
  EXECUTE format(
    'INSERT INTO %I."workflowVersion" (id,"workflowId",status,name,trigger,steps,position) VALUES ($1,$2,$3,$4,$5,$6,$7)',
    ws) USING v2_id, wf2_id, 'ACTIVE'::"workspace_4qo1qwg02dcej8j8vi6yp7qsx"."workflowVersion_status_enum", 'v1', trig2, steps2, 1;
  EXECUTE format(
    'INSERT INTO %I."workflowVersion" (id,"workflowId",status,name,trigger,steps,position) VALUES ($1,$2,$3,$4,$5,$6,$7)',
    ws) USING v3_id, wf3_id, 'ACTIVE'::"workspace_4qo1qwg02dcej8j8vi6yp7qsx"."workflowVersion_status_enum", 'v1', trig3, steps3, 1;
  EXECUTE format(
    'INSERT INTO %I."workflowVersion" (id,"workflowId",status,name,trigger,steps,position) VALUES ($1,$2,$3,$4,$5,$6,$7)',
    ws) USING v4_id, wf4_id, 'ACTIVE'::"workspace_4qo1qwg02dcej8j8vi6yp7qsx"."workflowVersion_status_enum", 'v1', trig4, steps4, 1;

  -- Insertar automated triggers (sin createdBySource/Name — usan defaults)
  EXECUTE format(
    'INSERT INTO %I."workflowAutomatedTrigger" (id,type,settings,"workflowId",position) VALUES ($1,$2,$3,$4,$5)',
    ws) USING at1_id,
    'DATABASE_EVENT'::"workspace_4qo1qwg02dcej8j8vi6yp7qsx"."workflowAutomatedTrigger_type_enum",
    '{"eventName":"tramite.created","objectType":"tramite"}'::jsonb, wf1_id, 1;
  EXECUTE format(
    'INSERT INTO %I."workflowAutomatedTrigger" (id,type,settings,"workflowId",position) VALUES ($1,$2,$3,$4,$5)',
    ws) USING at2_id,
    'DATABASE_EVENT'::"workspace_4qo1qwg02dcej8j8vi6yp7qsx"."workflowAutomatedTrigger_type_enum",
    '{"eventName":"tramite.created","objectType":"tramite"}'::jsonb, wf2_id, 2;
  EXECUTE format(
    'INSERT INTO %I."workflowAutomatedTrigger" (id,type,settings,"workflowId",position) VALUES ($1,$2,$3,$4,$5)',
    ws) USING at3_id,
    'DATABASE_EVENT'::"workspace_4qo1qwg02dcej8j8vi6yp7qsx"."workflowAutomatedTrigger_type_enum",
    '{"eventName":"tramite.created","objectType":"tramite"}'::jsonb, wf3_id, 3;
  EXECUTE format(
    'INSERT INTO %I."workflowAutomatedTrigger" (id,type,settings,"workflowId",position) VALUES ($1,$2,$3,$4,$5)',
    ws) USING at4_id,
    'CRON'::"workspace_4qo1qwg02dcej8j8vi6yp7qsx"."workflowAutomatedTrigger_type_enum",
    '{"type":"CUSTOM","pattern":"0 8 * * *"}'::jsonb, wf4_id, 4;

  RAISE NOTICE 'Workflows recreados con UUIDs validos: WF1=% WF2=% WF3=% WF4=%',
    wf1_id, wf2_id, wf3_id, wf4_id;
END $BLOCK$;
