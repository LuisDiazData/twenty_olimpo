/**
 * setup-bandeja-view.mjs
 * Crea la vista "Bandeja de entrada — Todos los ramos" en el objeto Trámite.
 *
 * Columnas: Folio, Agente titular, Tipo, Ramo, Especialista, Estado, Fecha entrada
 * Orden: fechaEntrada descendente
 * Propósito: vista para directora y gerentes (sin filtro de especialista)
 *
 * Uso: node scripts/setup-bandeja-view.mjs
 */

const BASE = 'http://localhost:3000';
const API_KEY =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1MDEzZDMwOS1jOTAyLTQzYzQtYWQ3MC05MzBjYzY1OWU0NzEiLCJ0eXBlIjoiQVBJX0tFWSIsIndvcmtzcGFjZUlkIjoiNTAxM2QzMDktYzkwMi00M2M0LWFkNzAtOTMwY2M2NTllNDcxIiwiaWF0IjoxNzc0NjY4MDQzLCJleHAiOjQ5MjgyNjgwNDMsImp0aSI6IjBkN2E1YTViLTFmYTUtNGI2Ny1iMzEwLWJkYWRiMzkyYTNmNSJ9.pA1yP_-XcSpGBz5LslLy40J6YUoXjMaBdb_3pcnV9zs';

const VIEW_NAME = 'Bandeja de entrada — Todos los ramos';

// Campos que deben aparecer en la vista, en orden de posición.
// Los nombres son los field.name de metadata (camelCase).
const DESIRED_FIELDS = [
  'folioInterno',       // Folio
  'agenteTitular',      // Agente titular (relation)
  'tipoTramite',        // Tipo
  'ramo',               // Ramo
  'especialistaAsignado', // Especialista (relation)
  'estadoTramite',      // Estado
  'fechaEntrada',       // Fecha entrada
];

// Campo de ordenación
const SORT_FIELD = 'fechaEntrada';
const SORT_DIRECTION = 'DescNullsLast';

async function metadataGQL(query, variables = {}) {
  const res = await fetch(`${BASE}/metadata`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${API_KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, variables }),
  });
  if (!res.ok) throw new Error(`Metadata GQL ${res.status}: ${await res.text()}`);
  const json = await res.json();
  if (json.errors?.length) throw new Error(`Metadata GQL error: ${JSON.stringify(json.errors[0])}`);
  return json.data;
}

async function workspaceGQL(query, variables = {}) {
  const res = await fetch(`${BASE}/api`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${API_KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, variables }),
  });
  if (!res.ok) throw new Error(`Workspace GQL ${res.status}: ${await res.text()}`);
  const json = await res.json();
  if (json.errors?.length) throw new Error(`Workspace GQL error: ${JSON.stringify(json.errors[0])}`);
  return json.data;
}

async function main() {
  console.log('═══════════════════════════════════════════════════════');
  console.log('  Setup: Bandeja de entrada — Todos los ramos');
  console.log('═══════════════════════════════════════════════════════\n');

  // ── 1. Obtener metadata del objeto tramite ────────────────────────────────
  console.log('1. Consultando metadata del objeto tramite...');
  const metaResult = await metadataGQL(`
    query {
      objects(paging: { first: 200 }) {
        edges {
          node {
            id
            nameSingular
            fields(paging: { first: 200 }) {
              edges {
                node {
                  id
                  name
                  label
                  type
                }
              }
            }
          }
        }
      }
    }
  `);

  const tramiteObj = metaResult.objects.edges
    .map((e) => e.node)
    .find((o) => o.nameSingular === 'tramite');

  if (!tramiteObj) {
    throw new Error(
      'Objeto "tramite" no encontrado en metadata. ' +
      'Verifica que el objeto esté creado en Settings > Data Model.',
    );
  }
  console.log(`   ✅ tramite object id: ${tramiteObj.id}`);

  const fieldsByName = Object.fromEntries(
    tramiteObj.fields.edges.map((e) => [e.node.name, e.node]),
  );

  // Mapeo de alias a nombre real (para manejar variaciones de nombre)
  const FIELD_ALIASES = {
    agenteTitular: ['agenteTitular', 'agenteTitularId', 'agente', 'agenteId'],
    especialistaAsignado: ['especialistaAsignado', 'especialistaAsignadoId', 'especialista'],
  };

  function resolveField(desiredName) {
    if (fieldsByName[desiredName]) return fieldsByName[desiredName];
    const aliases = FIELD_ALIASES[desiredName] ?? [];
    for (const alias of aliases) {
      if (fieldsByName[alias]) return fieldsByName[alias];
    }
    return null;
  }

  console.log('\n2. Verificando campos requeridos...');
  const resolvedFields = [];
  for (const name of DESIRED_FIELDS) {
    const field = resolveField(name);
    if (field) {
      console.log(`   ✅ ${name} → field id: ${field.id} (${field.type})`);
      resolvedFields.push(field);
    } else {
      console.warn(`   ⚠️  Campo "${name}" no encontrado — se omitirá de la vista`);
      console.log(`      Campos disponibles: ${Object.keys(fieldsByName).join(', ')}`);
    }
  }

  if (resolvedFields.length === 0) {
    throw new Error('Ningún campo resuelto. Verifica los nombres de campos del objeto tramite.');
  }

  // ── 2. Verificar si la vista ya existe ────────────────────────────────────
  console.log(`\n3. Verificando si la vista "${VIEW_NAME}" ya existe...`);
  const existingViews = await workspaceGQL(`
    query {
      views(filter: { name: { eq: "${VIEW_NAME.replace(/"/g, '\\"')}" } }) {
        edges {
          node {
            id
            name
          }
        }
      }
    }
  `).catch(() => ({ views: { edges: [] } }));

  const existingView = existingViews?.views?.edges?.[0]?.node;
  if (existingView) {
    console.log(`   ⚠️  Vista ya existe (id: ${existingView.id}) — eliminando para recrear...`);
    await workspaceGQL(`
      mutation {
        deleteView(id: "${existingView.id}") { id }
      }
    `).catch((e) => console.warn('   No se pudo eliminar la vista existente:', e.message));
  }

  // ── 3. Crear la vista ─────────────────────────────────────────────────────
  console.log(`\n4. Creando vista "${VIEW_NAME}"...`);
  const createViewResult = await workspaceGQL(`
    mutation CreateView($data: ViewCreateInput!) {
      createView(data: $data) {
        id
        name
      }
    }
  `, {
    data: {
      name: VIEW_NAME,
      objectMetadataId: tramiteObj.id,
      type: 'TABLE',
    },
  });

  const viewId = createViewResult.createView?.id;
  if (!viewId) throw new Error(`createView no devolvió id: ${JSON.stringify(createViewResult)}`);
  console.log(`   ✅ Vista creada: id=${viewId}`);

  // ── 4. Crear campos de la vista ───────────────────────────────────────────
  console.log('\n5. Configurando columnas...');
  const viewFieldsData = resolvedFields.map((field, idx) => ({
    viewId,
    fieldMetadataId: field.id,
    position: idx,
    isVisible: true,
    size: field.name === 'folioInterno' ? 160 : field.name === 'fechaEntrada' ? 140 : 180,
  }));

  const createFieldsResult = await workspaceGQL(`
    mutation CreateViewFields($data: [ViewFieldCreateInput!]!) {
      createViewFields(data: $data) {
        id
        position
      }
    }
  `, { data: viewFieldsData });

  const createdFields = createFieldsResult.createViewFields ?? [];
  console.log(`   ✅ ${createdFields.length} columnas configuradas`);

  // ── 5. Crear ordenación ───────────────────────────────────────────────────
  const sortField = resolveField(SORT_FIELD);
  if (sortField) {
    console.log(`\n6. Configurando ordenación por ${SORT_FIELD} descendente...`);
    await workspaceGQL(`
      mutation CreateViewSort($data: ViewSortCreateInput!) {
        createViewSort(data: $data) {
          id
        }
      }
    `, {
      data: {
        viewId,
        fieldMetadataId: sortField.id,
        direction: SORT_DIRECTION,
      },
    }).catch((e) => console.warn('   ⚠️  Sort no aplicado (no fatal):', e.message));
    console.log('   ✅ Ordenación configurada');
  }

  // ── Resumen ───────────────────────────────────────────────────────────────
  console.log('\n═══════════════════════════════════════════════════════');
  console.log('  ✅ Vista creada exitosamente');
  console.log(`  Nombre: ${VIEW_NAME}`);
  console.log(`  ID: ${viewId}`);
  console.log('  Columnas: ' + resolvedFields.map((f) => f.label || f.name).join(', '));
  console.log('  Orden: fechaEntrada descendente');
  console.log('\n  Accede en: http://localhost:3000 → Trámites → cambiar vista');
  console.log('═══════════════════════════════════════════════════════\n');
}

main().catch((err) => {
  console.error('\n❌ Error:', err.message);
  process.exit(1);
});
