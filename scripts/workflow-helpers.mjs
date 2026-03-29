/**
 * Workflow Helpers Server — port 4000
 * Handles computation-heavy logic for Twenty CRM workflows:
 *   POST /auto-folio        — Genera folioInterno TRM-YYYY-NNNN para un trámite recién creado
 *   POST /auto-sla          — Calcula fechaLimiteSla según el ramo y la fechaEntrada
 *   POST /auto-assign       — Asigna especialista según agente+ramo
 *   POST /mark-overdue-sla  — Cron: marca fueraDeSla=true donde SLA vencido
 *   POST /email-to-tramite  — Gmail sync: vincula email a trámite existente o crea uno nuevo
 *
 * Arranca con: node scripts/workflow-helpers.mjs
 */

import http from 'node:http';

const TWENTY_URL = 'http://localhost:3000';
const API_KEY =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1MDEzZDMwOS1jOTAyLTQzYzQtYWQ3MC05MzBjYzY1OWU0NzEiLCJ0eXBlIjoiQVBJX0tFWSIsIndvcmtzcGFjZUlkIjoiNTAxM2QzMDktYzkwMi00M2M0LWFkNzAtOTMwY2M2NTllNDcxIiwiaWF0IjoxNzc0NjY4MDQzLCJleHAiOjQ5MjgyNjgwNDMsImp0aSI6IjBkN2E1YTViLTFmYTUtNGI2Ny1iMzEwLWJkYWRiMzkyYTNmNSJ9.pA1yP_-XcSpGBz5LslLy40J6YUoXjMaBdb_3pcnV9zs';

// SLA en días hábiles por ramo
const SLA_DIAS = {
  VIDA: 3,
  GMM: 3,
  AUTOS: 2,
  PYME: 5,
  PYMC: 5,
  DANOS: 4,
};

async function twentyGraphQL(query, variables = {}) {
  const res = await fetch(`${TWENTY_URL}/api`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ query, variables }),
  });
  if (!res.ok) throw new Error(`GraphQL ${res.status}`);
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

/** Suma días hábiles a una fecha (excluye sábado=6, domingo=0) */
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

async function handleAutoFolio(tramiteId) {
  const year = new Date().getFullYear();
  const yearStart = `${year}-01-01T00:00:00.000Z`;

  // Contar trámites del año actual
  const resp = await twentyGet(
    `/rest/tramites?filter=createdAt[gte]:${encodeURIComponent(yearStart)}&limit=1`,
  );
  const count = resp.totalCount ?? 0;
  const folio = `TRM-${year}-${String(count + 1).padStart(4, '0')}`;

  await twentyPatch(`/rest/tramites/${tramiteId}`, { folioInterno: folio });
  return { folio };
}

async function handleAutoAssign(tramiteId, agenteTitularId, ramo) {
  if (!agenteTitularId || !ramo) {
    return { skipped: true, reason: 'sin agente o sin ramo' };
  }

  const ramoKey = (ramo ?? '').toUpperCase().replace(/\s/g, '_');
  const filter = `filter=and(asignacionActiva[eq]:true,ramo[eq]:${ramoKey},agenteId[eq]:${agenteTitularId})&limit=1`;
  const resp = await twentyGet(`/rest/asignaciones?${filter}`);
  const records = resp.data?.asignaciones ?? [];

  if (records.length === 0) {
    return { skipped: true, reason: 'sin asignacion activa para agente+ramo' };
  }

  const especialistaId = records[0].especialistaId;
  if (!especialistaId) {
    return { skipped: true, reason: 'asignacion sin especialista' };
  }

  await twentyPatch(`/rest/tramites/${tramiteId}`, { especialistaAsignadoId: especialistaId });
  return { especialistaId };
}

async function handleMarkOverdueSla() {
  const now = new Date().toISOString();
  // Fetch tramites where fueraDeSla=false and fechaLimiteSla < now (not closed)
  const filter = [
    `filter=and(fueraDeSla[eq]:false,fechaLimiteSla[lt]:${encodeURIComponent(now)},estadoTramite[neq]:CERRADO,estadoTramite[neq]:APROBADO_GNP)`,
  ].join('&');
  const resp = await twentyGet(`/rest/tramites?${filter}&limit=200`);
  const records = resp.data?.tramites ?? [];
  let marked = 0;
  for (const rec of records) {
    await twentyPatch(`/rest/tramites/${rec.id}`, { fueraDeSla: true });
    marked++;
  }
  return { marked };
}

async function handleAutoSla(tramiteId, ramo, fechaEntrada) {
  const ramoKey = (ramo ?? '').toUpperCase().replace(/\s/g, '_');
  const dias = SLA_DIAS[ramoKey] ?? 3; // default 3 días si ramo desconocido
  const base = fechaEntrada ? new Date(fechaEntrada) : new Date();
  const fechaLimiteSla = addBusinessDays(base, dias);

  await twentyPatch(`/rest/tramites/${tramiteId}`, { fechaLimiteSla });
  return { fechaLimiteSla, dias };
}

/**
 * POST /email-to-tramite
 * Llamado por un workflow de Twenty cuando se crea un Message (Gmail sync).
 * Lógica:
 *   1. Obtiene participantes del mensaje para encontrar el remitente (role=FROM)
 *   2. Busca un Person (Contacto) cuyo primaryEmail coincida
 *   3. Si el contacto tiene un trámite activo → adjunta nota al trámite
 *   4. Si no tiene trámite activo → crea un trámite nuevo y llama /auto-assign
 *
 * Body: { messageId: string }
 */
async function handleEmailToTramite(messageId) {
  // ── 1. Obtener participante FROM ──────────────────────────────────────────
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

  // ── 2. Buscar Contacto (Person) por email ─────────────────────────────────
  const peopleResp = await twentyGet(
    `/rest/people?filter=emails.primaryEmail[eq]:${encodeURIComponent(fromEmail)}&limit=1`,
  );
  const people = peopleResp.data?.people ?? [];
  if (people.length === 0) {
    return { skipped: true, reason: `no contact with email ${fromEmail}` };
  }
  const contact = people[0];
  const contactId = contact.id;
  const agenteTitularId = contact.companyId ?? null; // Company del contacto = Agente titular

  // ── 3. Buscar trámite activo del contacto ─────────────────────────────────
  // "Activo" = estadoTramite no es CERRADO ni APROBADO_GNP
  const tramitesResp = await twentyGet(
    `/rest/tramites?filter=and(enviadoPorId[eq]:${contactId},estadoTramite[neq]:CERRADO,estadoTramite[neq]:APROBADO_GNP)&orderBy=createdAt[desc]&limit=1`,
  );
  const tramites = tramitesResp.data?.tramites ?? [];

  if (tramites.length > 0) {
    // ── 3a. Trámite activo encontrado → adjuntar nota ─────────────────────
    const tramite = tramites[0];
    const tramiteId = tramite.id;

    // Obtener asunto del mensaje
    const msgResp = await twentyGet(`/rest/messages/${messageId}`);
    const subject = msgResp.data?.message?.subject ?? '(sin asunto)';
    const fechaHoy = new Date().toISOString().slice(0, 10);

    // Crear nota vinculada al trámite
    const noteBody = `📧 Email recibido (${fechaHoy})\nDe: ${fromEmail}\nAsunto: ${subject}\nMensaje ID: ${messageId}`;
    try {
      const noteResp = await fetch(`${TWENTY_URL}/rest/notes`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${API_KEY}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ body: noteBody }),
      });
      if (noteResp.ok) {
        const noteData = await noteResp.json();
        const noteId = noteData.data?.note?.id ?? noteData.data?.createNote?.id;
        if (noteId) {
          // Vincular nota al trámite via noteTargets
          await fetch(`${TWENTY_URL}/rest/noteTargets`, {
            method: 'POST',
            headers: {
              Authorization: `Bearer ${API_KEY}`,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ noteId, tramiteId }),
          }).catch(() => {}); // no fatal si falla el link
        }
      }
    } catch (noteErr) {
      console.warn('[email-to-tramite] Note creation failed:', noteErr.message);
    }

    return {
      action: 'linked',
      tramiteId,
      folioInterno: tramite.folioInterno,
      fromEmail,
      contactId,
    };
  }

  // ── 4. Sin trámite activo → crear uno nuevo ───────────────────────────────
  const fechaEntrada = new Date().toISOString().slice(0, 10);
  const newTramitePayload = {
    estadoTramite: 'PENDIENTE',
    tipoTramite: 'NUEVA_POLIZA', // default; el especialista lo ajustará
    fechaEntrada,
    enviadoPorId: contactId,
    ...(agenteTitularId ? { agenteTitularId } : {}),
  };

  // Intentar setear canalIngreso=CORREO si el campo existe
  try {
    newTramitePayload.canalIngreso = 'CORREO';
  } catch {}

  const createResp = await fetch(`${TWENTY_URL}/rest/tramites`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(newTramitePayload),
  });
  const createData = await createResp.json();
  const newTramite = createData.data?.tramite ?? createData.data?.createTramite;
  if (!newTramite?.id) {
    throw new Error(`Failed to create tramite: ${JSON.stringify(createData)}`);
  }
  const newTramiteId = newTramite.id;

  // Llamar auto-folio, auto-sla y auto-assign encadenados
  await handleAutoFolio(newTramiteId).catch((e) =>
    console.warn('[email-to-tramite] auto-folio failed:', e.message),
  );
  await handleAutoAssign(newTramiteId, agenteTitularId, null).catch((e) =>
    console.warn('[email-to-tramite] auto-assign failed:', e.message),
  );

  return {
    action: 'created',
    tramiteId: newTramiteId,
    fromEmail,
    contactId,
    agenteTitularId,
  };
}

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

  try {
    const body = await readBody(req);
    console.log(`[${new Date().toISOString()}] ${req.method} ${req.url}`, body);

    if (req.method === 'POST' && req.url === '/auto-folio') {
      const { tramiteId } = body;
      if (!tramiteId) {
        res.writeHead(400);
        return res.end(JSON.stringify({ error: 'tramiteId requerido' }));
      }
      const result = await handleAutoFolio(tramiteId);
      res.writeHead(200);
      return res.end(JSON.stringify({ ok: true, ...result }));
    }

    if (req.method === 'POST' && req.url === '/auto-sla') {
      const { tramiteId, ramo, fechaEntrada } = body;
      if (!tramiteId || !ramo) {
        res.writeHead(400);
        return res.end(JSON.stringify({ error: 'tramiteId y ramo requeridos' }));
      }
      const result = await handleAutoSla(tramiteId, ramo, fechaEntrada);
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
      res.writeHead(200);
      return res.end(JSON.stringify({ ok: true, ...result }));
    }

    if (req.method === 'POST' && req.url === '/mark-overdue-sla') {
      const result = await handleMarkOverdueSla();
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
      res.writeHead(200);
      return res.end(JSON.stringify({ ok: true, ...result }));
    }

    if (req.method === 'GET' && req.url === '/health') {
      res.writeHead(200);
      return res.end(JSON.stringify({ status: 'ok' }));
    }

    res.writeHead(404);
    res.end(JSON.stringify({ error: 'Not found' }));
  } catch (err) {
    console.error('Error:', err.message);
    res.writeHead(500);
    res.end(JSON.stringify({ error: err.message }));
  }
});

server.listen(4000, () => {
  console.log('Workflow helpers server listening on http://localhost:4000');
  console.log('  POST /auto-folio          { tramiteId }');
  console.log('  POST /auto-assign         { tramiteId, agenteTitularId, ramo }');
  console.log('  POST /auto-sla            { tramiteId, ramo, fechaEntrada }');
  console.log('  POST /mark-overdue-sla    {}');
  console.log('  POST /email-to-tramite    { messageId }');
});
