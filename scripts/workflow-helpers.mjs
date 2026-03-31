/**
 * Workflow Helpers Server — port 4000
 * Handles computation-heavy logic for Twenty CRM workflows:
 *   POST /auto-folio        — Genera folioInterno TRM-YYYY-NNNNN para un trámite recién creado
 *   POST /auto-sla          — Calcula fechaLimiteSla según ramo+tipoTramite y fechaEntrada
 *   POST /auto-assign       — Asigna especialista según agente+ramo
 *   POST /mark-overdue-sla  — Cron: marca fueraDeSla=true donde SLA vencido
 *   POST /email-to-tramite  — Gmail sync: vincula email a trámite existente o crea uno nuevo
 *
 * Arrancar con:
 *   node --env-file=.env scripts/workflow-helpers.mjs
 *
 * Variables de entorno requeridas (en /.env raíz):
 *   TWENTY_API_URL   — URL del servidor Twenty (default: http://localhost:3000)
 *   TWENTY_API_KEY   — API Key del workspace
 *   HELPER_PORT      — Puerto del servidor (default: 4000)
 *   SLA_CONFIG       — JSON con días hábiles por ramo y tipo de trámite (opcional, usa defaults si no está)
 */

import http from 'node:http';

const TWENTY_URL = process.env.TWENTY_API_URL ?? 'http://localhost:3000';
const API_KEY    = process.env.TWENTY_API_KEY ?? '';
const HELPER_PORT = parseInt(process.env.HELPER_PORT ?? '4000', 10);

if (!API_KEY) {
  console.warn('[WARN] TWENTY_API_KEY no está configurada. Las llamadas a Twenty fallarán.');
}

// ─── Configuración de SLA ────────────────────────────────────────────────────
// Días hábiles por ramo + tipo de trámite.
// Formato: { "RAMO": { "default": N, "TIPO_TRAMITE": N } }
// Tipos válidos: NUEVA_POLIZA, ENDOSO, RENOVACION, CANCELACION, SINIESTRO, COTIZACION_PYME
const DEFAULT_SLA = {
  VIDA:  { default: 5, SINIESTRO: 3 },
  GMM:   { default: 3, SINIESTRO: 2 },
  AUTOS: { default: 4, SINIESTRO: 2 },
  PYME:  { default: 7, SINIESTRO: 3 },
  DANOS: { default: 5, SINIESTRO: 3 },
};

function loadSlaConfig() {
  const raw = process.env.SLA_CONFIG;
  if (raw) {
    try {
      return JSON.parse(raw);
    } catch {
      console.warn('[WARN] SLA_CONFIG tiene JSON inválido — usando valores por defecto.');
    }
  }
  return DEFAULT_SLA;
}

const SLA_CONFIG = loadSlaConfig();

function getSlaDays(ramo, tipoTramite) {
  const ramoKey = (ramo ?? '').toUpperCase().replace(/\s+/g, '_');
  const tipoKey = (tipoTramite ?? '').toUpperCase().replace(/\s+/g, '_');
  const ramoConfig = SLA_CONFIG[ramoKey];
  if (!ramoConfig) return 3; // default global si ramo desconocido
  return ramoConfig[tipoKey] ?? ramoConfig.default ?? 3;
}

// ─── Clientes HTTP Twenty ────────────────────────────────────────────────────

async function twentyGraphQL(query, variables = {}) {
  const res = await fetch(`${TWENTY_URL}/api`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ query, variables }),
  });
  if (!res.ok) throw new Error(`GraphQL HTTP ${res.status}`);
  const json = await res.json();
  if (json.errors?.length) throw new Error(json.errors[0].message);
  return json.data;
}

async function twentyGet(path) {
  const url = `${TWENTY_URL}${path}`;
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${API_KEY}` },
  });
  if (!res.ok) throw new Error(`GET ${url} → ${res.status}`);
  return res.json();
}

async function twentyPatch(path, body) {
  const url = `${TWENTY_URL}${path}`;
  const res = await fetch(url, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`PATCH ${url} → ${res.status}: ${text}`);
  }
  return res.json();
}

async function twentyPost(path, body) {
  const url = `${TWENTY_URL}${path}`;
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`POST ${url} → ${res.status}: ${text}`);
  }
  return res.json();
}

// ─── Días hábiles ────────────────────────────────────────────────────────────

/** Suma N días hábiles a una fecha (excluye sábado=6, domingo=0) */
function addBusinessDays(startDate, days) {
  const date = new Date(startDate);
  let added = 0;
  while (added < days) {
    date.setDate(date.getDate() + 1);
    const dow = date.getDay();
    if (dow !== 0 && dow !== 6) added++;
  }
  return date.toISOString().split('T')[0]; // YYYY-MM-DD
}

// ─── Handlers ────────────────────────────────────────────────────────────────

/**
 * Genera folioInterno único TRM-YYYY-NNNNN.
 * Busca el folio más alto del año actual (no cuenta registros, evita duplicados
 * si se eliminan trámites).
 */
async function handleAutoFolio(tramiteId) {
  const year = new Date().getFullYear();
  const prefix = `TRM-${year}-`;

  const resp = await twentyGet(
    `/rest/tramites?filter=folioInterno[like]:${encodeURIComponent(prefix + '%')}&orderBy=folioInterno[desc]&limit=1`,
  );
  const records = resp.data?.tramites ?? [];

  let nextNum = 1;
  if (records.length > 0 && records[0].folioInterno) {
    const match = records[0].folioInterno.match(/TRM-\d{4}-(\d+)/);
    if (match) nextNum = parseInt(match[1], 10) + 1;
  }

  const folio = `${prefix}${String(nextNum).padStart(5, '0')}`;
  await twentyPatch(`/rest/tramites/${tramiteId}`, { folioInterno: folio });
  return { folio };
}

/**
 * Calcula fechaLimiteSla según ramo + tipoTramite.
 * Si tipoTramite no viene en el body, lo obtiene del propio trámite.
 */
async function handleAutoSla(tramiteId, ramo, tipoTramite, fechaEntrada) {
  // Obtener tipoTramite del trámite si no vino en el body
  if (!tipoTramite) {
    const tramiteResp = await twentyGet(`/rest/tramites/${tramiteId}`);
    tipoTramite = tramiteResp.data?.tramite?.tipoTramite ?? null;
  }

  const dias = getSlaDays(ramo, tipoTramite);
  const base = fechaEntrada ? new Date(fechaEntrada) : new Date();
  const fechaLimiteSla = addBusinessDays(base, dias);

  await twentyPatch(`/rest/tramites/${tramiteId}`, { fechaLimiteSla });
  return { fechaLimiteSla, dias, ramo, tipoTramite };
}

/**
 * Asigna especialista buscando en la tabla Asignacion por agente+ramo.
 * Si no hay asignación: marca estadoTramite = EN_REVISION y agrega nota.
 */
async function handleAutoAssign(tramiteId, agenteTitularId, ramo) {
  if (!agenteTitularId || !ramo) {
    return { skipped: true, reason: 'sin agente o sin ramo' };
  }

  const ramoKey = ramo.toUpperCase().replace(/\s+/g, '_');
  const filter = `filter=and(asignacionActiva[eq]:true,ramo[eq]:${ramoKey},agenteId[eq]:${agenteTitularId})&limit=1`;
  const resp = await twentyGet(`/rest/asignaciones?${filter}`);
  const records = resp.data?.asignaciones ?? [];

  if (records.length === 0) {
    // Sin asignación: marcar para revisión manual
    await twentyPatch(`/rest/tramites/${tramiteId}`, {
      estadoTramite: 'EN_REVISION',
      notasAnalista: `Sin asignación configurada para agente ${agenteTitularId} / ramo ${ramoKey}. Asignar manualmente.`,
    });
    return { asignado: false, especialistaId: null, reason: 'sin asignacion activa para agente+ramo' };
  }

  const especialistaId = records[0].especialistaId;
  if (!especialistaId) {
    return { asignado: false, especialistaId: null, reason: 'asignacion sin especialista' };
  }

  await twentyPatch(`/rest/tramites/${tramiteId}`, { especialistaAsignadoId: especialistaId });
  return { asignado: true, especialistaId };
}

/**
 * Marca fueraDeSla=true en todos los trámites con SLA vencido que no estén cerrados.
 * Excluye: CERRADO, APROBADO_GNP, CANCELADO, RECHAZADO_GNP.
 */
async function handleMarkOverdueSla() {
  const now = new Date().toISOString();

  const filter = [
    `fueraDeSla[eq]:false`,
    `fechaLimiteSla[lt]:${encodeURIComponent(now)}`,
    `estadoTramite[neq]:CERRADO`,
    `estadoTramite[neq]:APROBADO_GNP`,
    `estadoTramite[neq]:CANCELADO`,
    `estadoTramite[neq]:RECHAZADO_GNP`,
  ].join(',');

  const resp = await twentyGet(`/rest/tramites?filter=and(${filter})&limit=200`);
  const records = resp.data?.tramites ?? [];

  // Filtrado defensivo en JS por si la API no soporta múltiples neq
  const estadosCerrados = new Set(['CERRADO', 'APROBADO_GNP', 'CANCELADO', 'RECHAZADO_GNP']);
  const pendientes = records.filter(
    (r) => !r.fueraDeSla && !estadosCerrados.has(r.estadoTramite),
  );

  let marcados = 0;
  for (const rec of pendientes) {
    await twentyPatch(`/rest/tramites/${rec.id}`, { fueraDeSla: true });
    marcados++;
  }
  return { marcados, evaluados: records.length };
}

/**
 * Vincula un mensaje de Gmail a un trámite existente (adjunta nota) o crea uno nuevo.
 * Body: { messageId: string }
 */
async function handleEmailToTramite(messageId) {
  // 1. Obtener participante FROM
  const participantsResp = await twentyGet(
    `/rest/messageParticipants?filter=and(messageId[eq]:${messageId},role[eq]:from)&limit=1`,
  );
  const participants = participantsResp.data?.messageParticipants ?? [];
  if (participants.length === 0) {
    return { skipped: true, reason: 'no FROM participant found' };
  }
  const fromEmail = participants[0].handle;
  if (!fromEmail) {
    return { skipped: true, reason: 'FROM participant has no email handle' };
  }

  // 2. Buscar Contacto (Person) por email
  const peopleResp = await twentyGet(
    `/rest/people?filter=emails.primaryEmail[eq]:${encodeURIComponent(fromEmail)}&limit=1`,
  );
  const people = peopleResp.data?.people ?? [];
  if (people.length === 0) {
    return { skipped: true, reason: `no contact with email ${fromEmail}` };
  }
  const contact = people[0];
  const contactId = contact.id;
  const agenteTitularId = contact.companyId ?? null;

  // 3. Buscar trámite activo del contacto
  const tramitesResp = await twentyGet(
    `/rest/tramites?filter=and(enviadoPorId[eq]:${contactId},estadoTramite[neq]:CERRADO,estadoTramite[neq]:APROBADO_GNP)&orderBy=createdAt[desc]&limit=1`,
  );
  const tramites = tramitesResp.data?.tramites ?? [];

  if (tramites.length > 0) {
    // 3a. Trámite activo encontrado → adjuntar nota
    const tramite = tramites[0];
    const tramiteId = tramite.id;
    const msgResp = await twentyGet(`/rest/messages/${messageId}`);
    const subject = msgResp.data?.message?.subject ?? '(sin asunto)';
    const fechaHoy = new Date().toISOString().slice(0, 10);

    const noteBody = `Email recibido (${fechaHoy})\nDe: ${fromEmail}\nAsunto: ${subject}\nMensaje ID: ${messageId}`;
    try {
      const noteData = await twentyPost('/rest/notes', { body: noteBody });
      const noteId = noteData.data?.note?.id ?? noteData.data?.createNote?.id;
      if (noteId) {
        await twentyPost('/rest/noteTargets', { noteId, tramiteId }).catch(() => {});
      }
    } catch (noteErr) {
      console.warn('[email-to-tramite] Note creation failed:', noteErr.message);
    }

    return { action: 'linked', tramiteId, folioInterno: tramite.folioInterno, fromEmail, contactId };
  }

  // 4. Sin trámite activo → crear uno nuevo
  const fechaEntrada = new Date().toISOString().slice(0, 10);
  const newTramitePayload = {
    estadoTramite: 'PENDIENTE',
    tipoTramite: 'NUEVA_POLIZA',
    fechaEntrada,
    enviadoPorId: contactId,
    ...(agenteTitularId ? { agenteTitularId } : {}),
  };

  const createData = await twentyPost('/rest/tramites', newTramitePayload);
  const newTramite = createData.data?.tramite ?? createData.data?.createTramite;
  if (!newTramite?.id) {
    throw new Error(`Failed to create tramite: ${JSON.stringify(createData)}`);
  }
  const newTramiteId = newTramite.id;

  await handleAutoFolio(newTramiteId).catch((e) =>
    console.warn('[email-to-tramite] auto-folio failed:', e.message),
  );
  await handleAutoAssign(newTramiteId, agenteTitularId, null).catch((e) =>
    console.warn('[email-to-tramite] auto-assign failed:', e.message),
  );

  return { action: 'created', tramiteId: newTramiteId, fromEmail, contactId, agenteTitularId };
}

// ─── Server ──────────────────────────────────────────────────────────────────

function readBody(req) {
  return new Promise((resolve, reject) => {
    let data = '';
    req.on('data', (chunk) => (data += chunk));
    req.on('end', () => {
      try {
        resolve(data ? JSON.parse(data) : {});
      } catch {
        reject(new Error('Invalid JSON body'));
      }
    });
    req.on('error', reject);
  });
}

const server = http.createServer(async (req, res) => {
  res.setHeader('Content-Type', 'application/json');
  const ts = new Date().toISOString();

  try {
    const body = await readBody(req);
    console.log(`[${ts}] ${req.method} ${req.url}`, JSON.stringify(body));

    if (req.method === 'GET' && req.url === '/health') {
      res.writeHead(200);
      return res.end(JSON.stringify({ status: 'ok', ts }));
    }

    if (req.method === 'POST' && req.url === '/auto-folio') {
      const { tramiteId } = body;
      if (!tramiteId) {
        res.writeHead(400);
        return res.end(JSON.stringify({ error: 'tramiteId requerido' }));
      }
      const result = await handleAutoFolio(tramiteId);
      console.log(`[${ts}] auto-folio OK`, result);
      res.writeHead(200);
      return res.end(JSON.stringify({ ok: true, ...result }));
    }

    if (req.method === 'POST' && req.url === '/auto-sla') {
      const { tramiteId, ramo, tipoTramite, fechaEntrada } = body;
      if (!tramiteId || !ramo) {
        res.writeHead(400);
        return res.end(JSON.stringify({ error: 'tramiteId y ramo requeridos' }));
      }
      const result = await handleAutoSla(tramiteId, ramo, tipoTramite, fechaEntrada);
      console.log(`[${ts}] auto-sla OK`, result);
      res.writeHead(200);
      return res.end(JSON.stringify({ ok: true, ...result }));
    }

    if (req.method === 'POST' && req.url === '/auto-assign') {
      const { tramiteId, agenteTitularId, ramo } = body;
      if (!tramiteId) {
        res.writeHead(400);
        return res.end(JSON.stringify({ error: 'tramiteId requerido' }));
      }
      const result = await handleAutoAssign(tramiteId, agenteTitularId, ramo);
      console.log(`[${ts}] auto-assign OK`, result);
      res.writeHead(200);
      return res.end(JSON.stringify({ ok: true, ...result }));
    }

    if (req.method === 'POST' && req.url === '/mark-overdue-sla') {
      const result = await handleMarkOverdueSla();
      console.log(`[${ts}] mark-overdue-sla OK`, result);
      res.writeHead(200);
      return res.end(JSON.stringify({ ok: true, ...result }));
    }

    if (req.method === 'POST' && req.url === '/email-to-tramite') {
      const { messageId } = body;
      if (!messageId) {
        res.writeHead(400);
        return res.end(JSON.stringify({ error: 'messageId requerido' }));
      }
      const result = await handleEmailToTramite(messageId);
      console.log(`[${ts}] email-to-tramite OK`, result);
      res.writeHead(200);
      return res.end(JSON.stringify({ ok: true, ...result }));
    }

    res.writeHead(404);
    res.end(JSON.stringify({ error: 'Not found' }));
  } catch (err) {
    console.error(`[${new Date().toISOString()}] ERROR ${req.url}:`, err.message);
    res.writeHead(500);
    res.end(JSON.stringify({ error: err.message }));
  }
});

server.listen(HELPER_PORT, '0.0.0.0', () => {
  console.log(`[${new Date().toISOString()}] Workflow helpers server escuchando en http://0.0.0.0:${HELPER_PORT}`);
  console.log(`  TWENTY_API_URL : ${TWENTY_URL}`);
  console.log(`  SLA_CONFIG     : ${JSON.stringify(SLA_CONFIG)}`);
  console.log('  Endpoints:');
  console.log('    GET  /health');
  console.log('    POST /auto-folio          { tramiteId }');
  console.log('    POST /auto-assign         { tramiteId, agenteTitularId, ramo }');
  console.log('    POST /auto-sla            { tramiteId, ramo, [tipoTramite], [fechaEntrada] }');
  console.log('    POST /mark-overdue-sla    {}');
  console.log('    POST /email-to-tramite    { messageId }');
});
