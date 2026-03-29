/**
 * test-workflows.mjs — Suite completa de pruebas para los 4 workflows
 *
 * WF1: Auto-folio         (tramite.created → genera folioInterno TRM-YYYY-NNNN)
 * WF2: Auto-asignación    (tramite.created → asigna especialistaAsignadoId)
 * WF3: Auto-SLA           (tramite.created → calcula fechaLimiteSla por ramo)
 * WF4: Cron fuera de SLA  (diario → marca fueraDeSla=true cuando SLA vencido)
 *
 * Uso: node scripts/test-workflows.mjs
 */

import http from 'node:http';

const TOKEN = process.env.TWENTY_TOKEN ||
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1MDEzZDMwOS1jOTAyLTQzYzQtYWQ3MC05MzBjYzY1OWU0NzEiLCJ0eXBlIjoiQVBJX0tFWSIsIndvcmtzcGFjZUlkIjoiNTAxM2QzMDktYzkwMi00M2M0LWFkNzAtOTMwY2M2NTllNDcxIiwiaWF0IjoxNzc0NzExMzcxLCJleHAiOjIwOTAwNzEzNzEsImp0aSI6IjBkN2E1YTViLTFmYTUtNGI2Ny1iMzEwLWJkYWRiMzkyYTNmNSJ9.vNsV41C2rS93v68JaztOSk7CqQovmBRUaNQyveNUgtc';
const BASE  = 'http://localhost:3000';
const HELPER = 'http://localhost:4000';

// ──── Datos de referencia ────────────────────────────────────────────────────
// Asignaciones activas en el sistema:
//   Ramirez → VIDA  → especialista 96fc35ea-4fa8-4388-956a-22ef62833c21
//   Lopez   → AUTOS → especialista 96fc35ea-4fa8-4388-956a-22ef62833c21
const AGENT_RAMIREZ = '84bb3677-ab99-4a55-9b9a-d6b2a275c6e7'; // VIDA asignacion
const AGENT_LOPEZ   = '2e8251c1-464a-4ec9-8c60-667aac3e0233'; // AUTOS asignacion
const ESP_96        = '96fc35ea-4fa8-4388-956a-22ef62833c21';

// SLA esperado desde hoy (2026-03-28 viernes)
const SLA = { VIDA:'2026-04-02', GMM:'2026-04-02', AUTOS:'2026-04-01', PYME:'2026-04-04', DANOS:'2026-04-03' };
const TODAY = '2026-03-28';

// ──── Utilidades ─────────────────────────────────────────────────────────────
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

async function api(method, path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: { Authorization: `Bearer ${TOKEN}`, 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  return res.json();
}

async function helper(path) {
  const res = await fetch(`${HELPER}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: '{}',
  });
  return res.json();
}

async function createTramite(fields) {
  const r = await api('POST', '/rest/tramites', {
    tipoTramite: 'NUEVA_POLIZA',
    estadoTramite: 'PENDIENTE',
    fechaEntrada: TODAY,
    ...fields,
  });
  // REST devuelve data.tramite o data.createTramite
  return r.data?.tramite ?? r.data?.createTramite;
}

async function getTramite(id) {
  const r = await api('GET', `/rest/tramites/${id}`);
  return r.data?.tramite;
}

async function patchTramite(id, fields) {
  const r = await api('PATCH', `/rest/tramites/${id}`, fields);
  return r.data?.tramite ?? r.data?.updateTramite;
}

async function deleteTramite(id) {
  await api('DELETE', `/rest/tramites/${id}`);
}

// ──── Framework mínimo de testing ────────────────────────────────────────────
let passed = 0, failed = 0;
const created = []; // IDs para limpiar al final

function assert(label, actual, expected) {
  const ok = actual === expected;
  const icon = ok ? '✅' : '❌';
  if (ok) {
    passed++;
    console.log(`  ${icon} ${label}`);
  } else {
    failed++;
    console.log(`  ${icon} ${label}`);
    console.log(`       esperado: ${expected}`);
    console.log(`       recibido: ${actual}`);
  }
}

function assertNotNull(label, actual) {
  const ok = actual !== null && actual !== undefined && actual !== '';
  const icon = ok ? '✅' : '❌';
  if (ok) { passed++; console.log(`  ${icon} ${label}: ${actual}`); }
  else     { failed++; console.log(`  ${icon} ${label}: NULO/VACÍO`); }
}

function assertNull(label, actual) {
  const ok = actual === null || actual === undefined;
  const icon = ok ? '✅' : '❌';
  if (ok) { passed++; console.log(`  ${icon} ${label}: (null) ✓`); }
  else     { failed++; console.log(`  ${icon} ${label}: esperaba null, recibió ${actual}`); }
}

// ──── TESTS ──────────────────────────────────────────────────────────────────

// ─── WF1: Auto-folio ─────────────────────────────────────────────────────────
async function testWF1() {
  console.log('\n━━━ WF1: Auto-folio TRM-YYYY-NNNN ━━━');
  const year = new Date().getFullYear();

  // T1: Folio generado al crear trámite
  console.log('\n  [T1] Trámite nuevo recibe folio automático');
  const t1 = await createTramite({ ramo: 'VIDA' });
  created.push(t1.id);
  await sleep(5000);
  const r1 = await getTramite(t1.id);
  assertNotNull('folioInterno generado', r1.folioInterno);
  assert('formato TRM-YYYY-', r1.folioInterno?.startsWith(`TRM-${year}-`), true);
  const n1 = parseInt(r1.folioInterno?.split('-')[2], 10);

  // T2: Segundo trámite tiene folio incremental
  console.log('\n  [T2] Folio incrementa con cada nuevo trámite');
  const t2 = await createTramite({ ramo: 'VIDA' });
  created.push(t2.id);
  await sleep(5000);
  const r2 = await getTramite(t2.id);
  assertNotNull('folioInterno generado', r2.folioInterno);
  const n2 = parseInt(r2.folioInterno?.split('-')[2], 10);
  assert('folio es mayor al anterior', n2 > n1, true);
  console.log(`       ${r1.folioInterno} → ${r2.folioInterno}`);
}

// ─── WF2: Auto-asignación ────────────────────────────────────────────────────
async function testWF2() {
  console.log('\n━━━ WF2: Auto-asignación de especialista ━━━');

  // T3: Agente Ramirez + VIDA → especialista asignado
  console.log('\n  [T3] Agente con asignacion activa (Ramirez/VIDA) → especialista asignado');
  const t3 = await createTramite({ ramo: 'VIDA', agenteTitularId: AGENT_RAMIREZ });
  created.push(t3.id);
  await sleep(5000);
  const r3 = await getTramite(t3.id);
  assert('especialistaAsignadoId correcto', r3.especialistaAsignadoId, ESP_96);

  // T4: Agente Lopez + AUTOS → especialista asignado
  console.log('\n  [T4] Agente con asignacion activa (Lopez/AUTOS) → especialista asignado');
  const t4 = await createTramite({ ramo: 'AUTOS', agenteTitularId: AGENT_LOPEZ });
  created.push(t4.id);
  await sleep(5000);
  const r4 = await getTramite(t4.id);
  assert('especialistaAsignadoId correcto', r4.especialistaAsignadoId, ESP_96);

  // T5: Agente Ramirez + DANOS (sin asignacion para ese ramo) → null, sin crash
  console.log('\n  [T5] Agente SIN asignacion para el ramo (Ramirez/DANOS) → null, sin crash');
  const t5 = await createTramite({ ramo: 'DANOS', agenteTitularId: AGENT_RAMIREZ });
  created.push(t5.id);
  await sleep(5000);
  const r5 = await getTramite(t5.id);
  assertNull('especialistaAsignadoId es null', r5.especialistaAsignadoId);
  assertNotNull('folioInterno generado (WF1 no crasheó)', r5.folioInterno);

  // T6: Sin agente (null) → null, sin crash
  console.log('\n  [T6] Sin agente (agenteTitularId null) → null, sin crash');
  const t6 = await createTramite({ ramo: 'VIDA' });
  created.push(t6.id);
  await sleep(5000);
  const r6 = await getTramite(t6.id);
  assertNull('especialistaAsignadoId es null', r6.especialistaAsignadoId);
  assertNotNull('folioInterno generado (WF1 no crasheó)', r6.folioInterno);
}

// ─── WF3: Auto-SLA ───────────────────────────────────────────────────────────
async function testWF3() {
  console.log('\n━━━ WF3: Auto-fecha límite SLA por ramo ━━━');
  console.log(`  Fecha entrada: ${TODAY} (viernes)`);

  for (const [ramo, expected] of Object.entries(SLA)) {
    console.log(`\n  [T-SLA-${ramo}] ramo=${ramo} → esperado ${expected}`);
    const t = await createTramite({ ramo, agenteTitularId: AGENT_RAMIREZ });
    created.push(t.id);
    await sleep(5000);
    const r = await getTramite(t.id);
    assert(`fechaLimiteSla = ${expected}`, r.fechaLimiteSla, expected);
  }
}

// ─── WF4: Cron fuera de SLA ──────────────────────────────────────────────────
async function testWF4() {
  console.log('\n━━━ WF4: Cron diario — marcar fuera de SLA ━━━');

  // Primero reset: asegurar que mark-overdue ya no tiene tramites nuevos que marcar
  await helper('/mark-overdue-sla');

  // T12: SLA vencido + estado activo → debe marcarse fueraDeSla=true
  console.log('\n  [T12] SLA vencido + estadoTramite activo → fueraDeSla=true');
  const t12 = await createTramite({ ramo: 'VIDA', agenteTitularId: AGENT_RAMIREZ });
  created.push(t12.id);
  await sleep(5000); // esperar WF3
  // Parchear SLA a fecha pasada y asegurar estado activo
  await patchTramite(t12.id, { fechaLimiteSla: '2025-01-01', fueraDeSla: false, estadoTramite: 'EN_REVISION' });
  await sleep(1000);
  const pre12 = await getTramite(t12.id);
  assert('setup: fechaLimiteSla en pasado', pre12.fechaLimiteSla, '2025-01-01');
  // Ejecutar el cron
  const res12 = await helper('/mark-overdue-sla');
  assert('helper reporta ≥1 marcado', res12.marked >= 1, true);
  const r12 = await getTramite(t12.id);
  assert('fueraDeSla = true', r12.fueraDeSla, true);

  // T13: SLA en el futuro → NO se marca
  console.log('\n  [T13] SLA en el futuro → fueraDeSla no cambia');
  const t13 = await createTramite({ ramo: 'VIDA', agenteTitularId: AGENT_RAMIREZ });
  created.push(t13.id);
  await sleep(5000);
  await patchTramite(t13.id, { fechaLimiteSla: '2030-12-31', fueraDeSla: false, estadoTramite: 'EN_REVISION' });
  await sleep(1000);
  await helper('/mark-overdue-sla');
  const r13 = await getTramite(t13.id);
  assert('fueraDeSla = false (SLA futuro no marcado)', r13.fueraDeSla, false);

  // T14: SLA vencido + estadoTramite=CERRADO → NO se marca
  console.log('\n  [T14] SLA vencido + estadoTramite=CERRADO → NO se marca');
  const t14 = await createTramite({ ramo: 'VIDA', agenteTitularId: AGENT_RAMIREZ });
  created.push(t14.id);
  await sleep(5000);
  await patchTramite(t14.id, { fechaLimiteSla: '2025-01-01', fueraDeSla: false, estadoTramite: 'CERRADO' });
  await sleep(1000);
  await helper('/mark-overdue-sla');
  const r14 = await getTramite(t14.id);
  assert('fueraDeSla = false (CERRADO excluido)', r14.fueraDeSla, false);

  // T15: SLA vencido + estadoTramite=APROBADO_GNP → NO se marca
  console.log('\n  [T15] SLA vencido + estadoTramite=APROBADO_GNP → NO se marca');
  const t15 = await createTramite({ ramo: 'VIDA', agenteTitularId: AGENT_RAMIREZ });
  created.push(t15.id);
  await sleep(5000);
  await patchTramite(t15.id, { fechaLimiteSla: '2025-01-01', fueraDeSla: false, estadoTramite: 'APROBADO_GNP' });
  await sleep(1000);
  await helper('/mark-overdue-sla');
  const r15 = await getTramite(t15.id);
  assert('fueraDeSla = false (APROBADO_GNP excluido)', r15.fueraDeSla, false);
}

// ─── Cleanup ──────────────────────────────────────────────────────────────────
async function cleanup() {
  console.log(`\n━━━ Limpieza: eliminando ${created.length} trámites de prueba ━━━`);
  for (const id of created) {
    try { await deleteTramite(id); } catch { /* ignore */ }
  }
  console.log('  Limpieza completada.');
}

// ─── Main ─────────────────────────────────────────────────────────────────────
(async () => {
  console.log('════════════════════════════════════════════════════');
  console.log('  TEST SUITE — Workflows de la Promotoría GNP');
  console.log('════════════════════════════════════════════════════');
  console.log(`  Base: ${BASE}  Helper: ${HELPER}`);

  // Verificar conectividad antes de correr
  try {
    const health = await fetch(`${HELPER}/health`);
    if (!health.ok) throw new Error('helper no responde');
  } catch {
    console.error('\n❌ FATAL: Helper server no está corriendo en puerto 4000.');
    console.error('   Inicia con: node scripts/workflow-helpers.mjs\n');
    process.exit(1);
  }

  const start = Date.now();
  try {
    await testWF1();
    await testWF2();
    await testWF3();
    await testWF4();
  } catch (err) {
    console.error('\n❌ ERROR inesperado:', err.message);
    failed++;
  } finally {
    await cleanup();
  }

  const elapsed = ((Date.now() - start) / 1000).toFixed(1);
  const total = passed + failed;
  console.log('\n════════════════════════════════════════════════════');
  console.log(`  RESULTADOS: ${passed}/${total} pasaron  (${elapsed}s)`);
  if (failed === 0) {
    console.log('  ✅ TODOS LOS WORKFLOWS FUNCIONAN CORRECTAMENTE');
  } else {
    console.log(`  ❌ ${failed} prueba(s) fallaron — revisar antes de producción`);
  }
  console.log('════════════════════════════════════════════════════\n');

  process.exit(failed > 0 ? 1 : 0);
})();
