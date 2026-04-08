"""
seed_datos_prueba.py
====================
Ingesta datos de prueba realistas en Twenty CRM y Supabase.

Cobertura en Twenty CRM:
  - Productos (5 productos GNP)
  - Agentes (6 agentes externos con diferentes niveles)
  - Colaboradores (3 sub-agentes)
  - Tramites (15 trámites en distintos estatus/ramos)
  - HistorialEstatus (trayectoria de cada trámite)
  - HilosConversacion (hilos de correo vinculados)
  - DocumentoTramite (documentos checklist)
  - AlertaTramite (notificaciones enviadas)

Cobertura en Supabase:
  - incoming_emails (10 correos entrantes)
  - tramites_pipeline (15 registros espejo)
  - attachments_log (documentos procesados)
  - historial_estatus (cambios de estatus)
  - notas_interacciones (interacciones por tramite)
  - cobertura_analistas (cobertura vacacional)
  - historial_asignaciones (log de asignaciones)
  - agent_performance_monthly (KPIs mensuales por agente)
  - kpi_snapshots_cache (métricas globales)

Uso:
  python3 scripts/seed_datos_prueba.py
"""

import json
import os
import sys
import time
import uuid
import urllib.request
import urllib.error
from datetime import datetime, timedelta, date
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────

env_path = Path(__file__).parent.parent / "packages/twenty-docker/.env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

TWENTY_KEY  = os.environ.get("TWENTY_API_KEY", "")
TWENTY_URL  = os.environ.get("TWENTY_API_URL", "http://localhost:3000")
GQL_URL     = f"{TWENTY_URL}/graphql"

SUPABASE_URL  = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY  = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not TWENTY_KEY:
    print("ERROR: TWENTY_API_KEY no encontrado"); sys.exit(1)
if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY no encontrado"); sys.exit(1)

TWENTY_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TWENTY_KEY}",
}
SUPABASE_HEADERS = {
    "Content-Type": "application/json",
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Prefer": "return=representation",
}

# IDs de workspace members reales (obtenidos de la instancia)
WS_MEMBER_ID = "72c46d48-128c-4a4b-a53e-00a7ce9e3a64"  # Luis Gonzalez (admin/director)


# ── Helpers ────────────────────────────────────────────────────────────────────

def gql(query: str, variables: dict = None) -> dict:
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    body = json.dumps(payload).encode()
    req = urllib.request.Request(GQL_URL, data=body, headers=TWENTY_HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        print(f"  HTTP {e.code}: {body_text[:400]}")
        return {}
    if "errors" in data:
        for err in data["errors"]:
            print(f"  GQL Error: {err.get('message')}")
        return {}
    return data.get("data", {})


def supabase_insert(table: str, rows: list[dict]) -> list[dict]:
    """Insert rows into a Supabase table, returns inserted rows."""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    body = json.dumps(rows).encode()
    req = urllib.request.Request(url, data=body, headers=SUPABASE_HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            return result if isinstance(result, list) else [result]
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        print(f"  Supabase {table} error {e.code}: {body_text[:400]}")
        return []


def now_iso(delta_days=0) -> str:
    dt = datetime.utcnow() + timedelta(days=delta_days)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def date_iso(delta_days=0) -> str:
    d = date.today() + timedelta(days=delta_days)
    return d.isoformat()


def ok(label: str, result) -> str:
    if result:
        id_val = result.get("id", "—") if isinstance(result, dict) else "✓"
        print(f"  ✓ {label} ({id_val})")
        return result.get("id", "") if isinstance(result, dict) else ""
    print(f"  ✗ {label} FALLÓ")
    return ""


# ── Twenty CRM seed ────────────────────────────────────────────────────────────

def seed_productos() -> list[str]:
    """Devuelve lista de IDs de productos creados."""
    print("\n► Productos")
    productos = [
        {"name": "Vida Individual Total GNP", "claveProducto": "VIDA_IND_TOTAL",
         "nombreProducto": "Vida Individual Total", "ramo": "VIDA",
         "descripcion": "Seguro de vida individual con cobertura por fallecimiento e invalidez total",
         "slaHorasDefault": 40.0, "activo": True},
        {"name": "GMM Flex GNP", "claveProducto": "GMM_FLEX",
         "nombreProducto": "Gastos Médicos Mayores Flex", "ramo": "GMM",
         "descripcion": "GMM individual con red amplia y deducible flexible",
         "slaHorasDefault": 24.0, "activo": True},
        {"name": "Auto Amplia GNP", "claveProducto": "AUTOS_AMPLIA",
         "nombreProducto": "Auto Amplia", "ramo": "AUTOS",
         "descripcion": "Cobertura amplia para autos con asistencia vial 24/7",
         "slaHorasDefault": 32.0, "activo": True},
        {"name": "Pyme Paquete Integral GNP", "claveProducto": "PYME_PAQUETE",
         "nombreProducto": "Pyme Paquete Integral", "ramo": "PYME",
         "descripcion": "Seguro multirriesgo empresarial: daños, RC y vida grupal",
         "slaHorasDefault": 56.0, "activo": True},
        {"name": "Daños Hogar GNP", "claveProducto": "DANOS_HOGAR",
         "nombreProducto": "Daños Hogar", "ramo": "DANOS",
         "descripcion": "Seguro de casa habitación contra robo, incendio y daños eléctricos",
         "slaHorasDefault": 40.0, "activo": True},
    ]
    ids = []
    for p in productos:
        result = gql("""
          mutation CreateProducto($data: ProductoCreateInput!) {
            createProducto(data: $data) { id }
          }
        """, {"data": p})
        node = result.get("createProducto")
        ids.append(ok(f"Producto {p['claveProducto']}", node))
        time.sleep(0.2)
    return ids


def seed_agentes() -> list[str]:
    """Devuelve lista de IDs de agentes creados."""
    print("\n► Agentes")
    agentes = [
        {"name": "Roberto Mendez Vega", "claveAgente": "GNP-001-MX",
         "rfc": "MEVR810512AB3", "cedula": "CNSF-2019-4521",
         "fechaAlta": "2019-03-15", "fechaVencimientoCedula": "2026-03-14",
         "nivel": "TOP", "estatusAgente": "ACTIVO", "tipoPersona": "PERSONA_FISICA",
         "ramos": ["VIDA", "GMM"], "promotoriaAsignada": "Promotoría Centro",
         "activo": True},
        {"name": "Carmen Reyes Fuentes", "claveAgente": "GNP-002-MX",
         "rfc": "REFC780920CD4", "cedula": "CNSF-2020-7834",
         "fechaAlta": "2020-06-01", "fechaVencimientoCedula": "2025-12-31",  # próxima a vencer!
         "nivel": "CONSOLIDADO", "estatusAgente": "ACTIVO", "tipoPersona": "PERSONA_FISICA",
         "ramos": ["GMM", "AUTOS"], "promotoriaAsignada": "Promotoría Norte",
         "activo": True},
        {"name": "Distribuidora Seguros Azteca SA de CV", "claveAgente": "GNP-003-MX",
         "rfc": "DSA950101EF5", "cedula": "CNSF-2021-9102",
         "fechaAlta": "2021-01-10", "fechaVencimientoCedula": "2027-01-09",
         "nivel": "CONSOLIDADO", "estatusAgente": "ACTIVO", "tipoPersona": "PERSONA_MORAL",
         "ramos": ["PYMES", "DANOS"], "promotoriaAsignada": "Promotoría Empresarial",
         "activo": True},
        {"name": "Jorge Salinas Montoya", "claveAgente": "GNP-004-MX",
         "rfc": "SAMJ900304GH6", "cedula": "CNSF-2022-5567",
         "fechaAlta": "2022-09-20", "fechaVencimientoCedula": "2026-09-19",
         "nivel": "ARRANQUE", "estatusAgente": "ACTIVO", "tipoPersona": "PERSONA_FISICA",
         "ramos": ["AUTOS"], "promotoriaAsignada": "Promotoría Norte",
         "activo": True},
        {"name": "Patricia Torres Luna", "claveAgente": "GNP-005-MX",
         "rfc": "TOLP851122IJ7", "cedula": "CNSF-2018-3398",
         "fechaAlta": "2018-11-05", "fechaVencimientoCedula": "2025-11-04",  # ¡vence en < 60 días!
         "nivel": "TOP", "estatusAgente": "ACTIVO", "tipoPersona": "PERSONA_FISICA",
         "ramos": ["VIDA", "GMM", "AUTOS", "DANOS"], "promotoriaAsignada": "Promotoría Sur",
         "activo": True},
        {"name": "Manuel Castro Ibañez", "claveAgente": "GNP-006-MX",
         "rfc": "CAIM720815KL8", "cedula": "CNSF-2023-1245",
         "fechaAlta": "2023-02-28", "fechaVencimientoCedula": "2028-02-27",
         "nivel": "ARRANQUE", "estatusAgente": "PROSPECTO", "tipoPersona": "PERSONA_FISICA",
         "ramos": ["VIDA"], "promotoriaAsignada": "Promotoría Centro",
         "activo": False},
    ]
    ids = []
    for a in agentes:
        result = gql("""
          mutation CreateAgente($data: AgenteCreateInput!) {
            createAgente(data: $data) { id }
          }
        """, {"data": a})
        node = result.get("createAgente")
        ids.append(ok(f"Agente {a['claveAgente']} — {a['name']}", node))
        time.sleep(0.2)
    return ids


def seed_colaboradores(agente_ids: list[str]) -> list[str]:
    """Crea sub-agentes bajo los primeros agentes."""
    print("\n► Colaboradores")
    if not agente_ids or not agente_ids[0]:
        print("  Sin IDs de agentes — omitiendo")
        return []
    colaboradores = [
        {"name": "Sandra Vela Reyes", "rfc": "VERS940210AB1",
         "curp": "VERS940210MMZLRN09", "claveColaborador": "COL-001",
         "rolColaborador": "ASISTENTE_ADMINISTRATIVO", "activo": True,
         "ramos": ["VIDA", "GMM"], "agentePrincipalId": agente_ids[0]},
        {"name": "Daniel Moreno Gil", "rfc": "MOGI890505CD2",
         "curp": "MOGI890505HDFRNL08", "claveColaborador": "COL-002",
         "rolColaborador": "SUB_AGENTE", "activo": True,
         "ramos": ["AUTOS"], "agentePrincipalId": agente_ids[1] if len(agente_ids) > 1 else agente_ids[0]},
        {"name": "Laura Espinoza Ramos", "rfc": "EIRL970818EF3",
         "curp": "EIRL970818MMZPMR02", "claveColaborador": "COL-003",
         "rolColaborador": "PROMOTOR_AUXILIAR", "activo": True,
         "ramos": ["PYMES", "DANOS"], "agentePrincipalId": agente_ids[2] if len(agente_ids) > 2 else agente_ids[0]},
    ]
    ids = []
    for c in colaboradores:
        result = gql("""
          mutation CreateColaborador($data: ColaboradorCreateInput!) {
            createColaborador(data: $data) { id }
          }
        """, {"data": c})
        node = result.get("createColaborador")
        ids.append(ok(f"Colaborador {c['claveColaborador']} — {c['name']}", node))
        time.sleep(0.2)
    return ids


def seed_tramites(agente_ids: list[str]) -> list[str]:
    """Crea 15 trámites en distintos estados y ramos."""
    print("\n► Trámites")
    if not agente_ids or not agente_ids[0]:
        print("  Sin IDs de agentes — omitiendo")
        return []

    def agente(i): return agente_ids[i % len(agente_ids)] if agente_ids[i % len(agente_ids)] else agente_ids[0]

    tramites_data = [
        # Vida — activos en distintos estatus
        {"name": "TRM-2026-001", "folio": "TRM-2026-001", "ramo": "VIDA", "tipoTramite": "EMISION",
         "estatus": "DOCUMENTACION_COMPLETA", "prioridad": "ALTA", "canalIngreso": "CORREO",
         "fechaIngreso": now_iso(-8), "fechaLimiteDocumentacion": date_iso(5),
         "monto": {"amountMicros": 8500000000, "currencyCode": "MXN"},
         "slaHoras": 40.0, "ubicacionTramite": "PROMOTORIA",
         "numeroPoliza": "", "notasInternas": {"blocknote": "[]"},
         "agenteId": agente(0), "analistaAsignadoId": WS_MEMBER_ID, "gerenteRamoId": WS_MEMBER_ID},

        {"name": "TRM-2026-002", "folio": "TRM-2026-002", "ramo": "VIDA", "tipoTramite": "SINIESTRO",
         "estatus": "EN_PROCESO_GNP", "prioridad": "URGENTE", "canalIngreso": "WHATSAPP",
         "fechaIngreso": now_iso(-15), "fechaTurnoGnp": now_iso(-10),
         "folioGnp": "GNP-SIN-2026-4421",
         "monto": {"amountMicros": 500000000000, "currencyCode": "MXN"},
         "slaHoras": 24.0, "ubicacionTramite": "GNP",
         "notasInternas": {"blocknote": "[]"},
         "agenteId": agente(0), "analistaAsignadoId": WS_MEMBER_ID, "gerenteRamoId": WS_MEMBER_ID},

        {"name": "TRM-2026-003", "folio": "TRM-2026-003", "ramo": "VIDA", "tipoTramite": "ENDOSO",
         "estatus": "DETENIDO", "prioridad": "ALTA", "canalIngreso": "CORREO",
         "fechaIngreso": now_iso(-22), "fechaTurnoGnp": now_iso(-18),
         "folioGnp": "GNP-END-2026-3311",
         "monto": {"amountMicros": 0, "currencyCode": "MXN"},
         "slaHoras": 40.0, "ubicacionTramite": "GNP",
         "notasInternas": {"blocknote": "[]"},
         "motivoDetencion": {"blocknote": "[]"},
         "agenteId": agente(0), "analistaAsignadoId": WS_MEMBER_ID, "gerenteRamoId": WS_MEMBER_ID},

        # GMM — flujo completo
        {"name": "TRM-2026-004", "folio": "TRM-2026-004", "ramo": "GMM", "tipoTramite": "EMISION",
         "estatus": "RECIBIDO", "prioridad": "NORMAL", "canalIngreso": "CORREO",
         "fechaIngreso": now_iso(-1),
         "monto": {"amountMicros": 12300000000, "currencyCode": "MXN"},
         "slaHoras": 24.0, "ubicacionTramite": "PROMOTORIA",
         "notasInternas": {"blocknote": "[]"},
         "agenteId": agente(1), "analistaAsignadoId": WS_MEMBER_ID, "gerenteRamoId": WS_MEMBER_ID},

        {"name": "TRM-2026-005", "folio": "TRM-2026-005", "ramo": "GMM", "tipoTramite": "RENOVACION",
         "estatus": "TURNADO_GNP", "prioridad": "NORMAL", "canalIngreso": "CORREO",
         "fechaIngreso": now_iso(-12), "fechaTurnoGnp": now_iso(-5),
         "folioGnp": "GNP-REN-2026-8872",
         "monto": {"amountMicros": 18500000000, "currencyCode": "MXN"},
         "slaHoras": 24.0, "ubicacionTramite": "GNP",
         "notasInternas": {"blocknote": "[]"},
         "agenteId": agente(1), "analistaAsignadoId": WS_MEMBER_ID, "gerenteRamoId": WS_MEMBER_ID},

        {"name": "TRM-2026-006", "folio": "TRM-2026-006", "ramo": "GMM", "tipoTramite": "EMISION",
         "estatus": "RESUELTO", "prioridad": "NORMAL", "canalIngreso": "CORREO",
         "fechaIngreso": now_iso(-30), "fechaTurnoGnp": now_iso(-25),
         "fechaResolucion": now_iso(-20), "folioGnp": "GNP-EMI-2026-2211",
         "numeroPoliza": "V-GNP-2026-22110",
         "monto": {"amountMicros": 9800000000, "currencyCode": "MXN"},
         "slaHoras": 24.0, "ubicacionTramite": "AGENTE",
         "notasInternas": {"blocknote": "[]"},
         "agenteId": agente(1), "analistaAsignadoId": WS_MEMBER_ID, "gerenteRamoId": WS_MEMBER_ID},

        # Autos
        {"name": "TRM-2026-007", "folio": "TRM-2026-007", "ramo": "AUTOS", "tipoTramite": "EMISION",
         "estatus": "EN_REVISION_DOC", "prioridad": "NORMAL", "canalIngreso": "WHATSAPP",
         "fechaIngreso": now_iso(-3),
         "monto": {"amountMicros": 4500000000, "currencyCode": "MXN"},
         "slaHoras": 32.0, "ubicacionTramite": "PROMOTORIA",
         "notasInternas": {"blocknote": "[]"},
         "agenteId": agente(3), "analistaAsignadoId": WS_MEMBER_ID, "gerenteRamoId": WS_MEMBER_ID},

        {"name": "TRM-2026-008", "folio": "TRM-2026-008", "ramo": "AUTOS", "tipoTramite": "SINIESTRO",
         "estatus": "EN_PROCESO_GNP", "prioridad": "URGENTE", "canalIngreso": "CORREO",
         "fechaIngreso": now_iso(-20), "fechaTurnoGnp": now_iso(-16),
         "folioGnp": "GNP-SIN-2026-7765",
         "monto": {"amountMicros": 85000000000, "currencyCode": "MXN"},
         "slaHoras": 24.0, "ubicacionTramite": "GNP",
         "notasInternas": {"blocknote": "[]"},
         "agenteId": agente(3), "analistaAsignadoId": WS_MEMBER_ID, "gerenteRamoId": WS_MEMBER_ID},

        {"name": "TRM-2026-009", "folio": "TRM-2026-009", "ramo": "AUTOS", "tipoTramite": "ENDOSO",
         "estatus": "RESUELTO", "prioridad": "NORMAL", "canalIngreso": "MANUAL",
         "fechaIngreso": now_iso(-45), "fechaTurnoGnp": now_iso(-40),
         "fechaResolucion": now_iso(-35), "folioGnp": "GNP-END-2026-1133",
         "monto": {"amountMicros": 0, "currencyCode": "MXN"},
         "slaHoras": 24.0, "ubicacionTramite": "AGENTE",
         "notasInternas": {"blocknote": "[]"},
         "agenteId": agente(3), "analistaAsignadoId": WS_MEMBER_ID, "gerenteRamoId": WS_MEMBER_ID},

        # PyMES
        {"name": "TRM-2026-010", "folio": "TRM-2026-010", "ramo": "PYMES", "tipoTramite": "EMISION",
         "estatus": "DOCUMENTACION_COMPLETA", "prioridad": "ALTA", "canalIngreso": "CORREO",
         "fechaIngreso": now_iso(-7), "fechaLimiteDocumentacion": date_iso(3),
         "monto": {"amountMicros": 45000000000, "currencyCode": "MXN"},
         "slaHoras": 56.0, "ubicacionTramite": "PROMOTORIA",
         "notasInternas": {"blocknote": "[]"},
         "agenteId": agente(2), "analistaAsignadoId": WS_MEMBER_ID, "gerenteRamoId": WS_MEMBER_ID},

        {"name": "TRM-2026-011", "folio": "TRM-2026-011", "ramo": "PYMES", "tipoTramite": "RENOVACION",
         "estatus": "CANCELADO", "prioridad": "NORMAL", "canalIngreso": "CORREO",
         "fechaIngreso": now_iso(-60), "fechaResolucion": now_iso(-55),
         "monto": {"amountMicros": 32000000000, "currencyCode": "MXN"},
         "slaHoras": 40.0, "ubicacionTramite": "AGENTE",
         "notasInternas": {"blocknote": "[]"},
         "agenteId": agente(2), "analistaAsignadoId": WS_MEMBER_ID, "gerenteRamoId": WS_MEMBER_ID},

        # Daños
        {"name": "TRM-2026-012", "folio": "TRM-2026-012", "ramo": "DANOS", "tipoTramite": "EMISION",
         "estatus": "RECIBIDO", "prioridad": "NORMAL", "canalIngreso": "CORREO",
         "fechaIngreso": now_iso(-2),
         "monto": {"amountMicros": 6200000000, "currencyCode": "MXN"},
         "slaHoras": 40.0, "ubicacionTramite": "PROMOTORIA",
         "notasInternas": {"blocknote": "[]"},
         "agenteId": agente(4), "analistaAsignadoId": WS_MEMBER_ID, "gerenteRamoId": WS_MEMBER_ID},

        {"name": "TRM-2026-013", "folio": "TRM-2026-013", "ramo": "DANOS", "tipoTramite": "SINIESTRO",
         "estatus": "DETENIDO", "prioridad": "URGENTE", "canalIngreso": "WHATSAPP",
         "fechaIngreso": now_iso(-35), "fechaTurnoGnp": now_iso(-30),
         "folioGnp": "GNP-SIN-2026-9934",
         "monto": {"amountMicros": 120000000000, "currencyCode": "MXN"},
         "slaHoras": 32.0, "ubicacionTramite": "GNP",
         "notasInternas": {"blocknote": "[]"},
         "motivoDetencion": {"blocknote": "[]"},
         "agenteId": agente(4), "analistaAsignadoId": WS_MEMBER_ID, "gerenteRamoId": WS_MEMBER_ID},

        {"name": "TRM-2026-014", "folio": "TRM-2026-014", "ramo": "VIDA", "tipoTramite": "RENOVACION",
         "estatus": "TURNADO_GNP", "prioridad": "NORMAL", "canalIngreso": "CORREO",
         "fechaIngreso": now_iso(-18), "fechaTurnoGnp": now_iso(-12),
         "folioGnp": "GNP-REN-2026-5521",
         "monto": {"amountMicros": 11200000000, "currencyCode": "MXN"},
         "slaHoras": 40.0, "ubicacionTramite": "GNP",
         "notasInternas": {"blocknote": "[]"},
         "agenteId": agente(4), "analistaAsignadoId": WS_MEMBER_ID, "gerenteRamoId": WS_MEMBER_ID},

        {"name": "TRM-2026-015", "folio": "TRM-2026-015", "ramo": "GMM", "tipoTramite": "EMISION",
         "estatus": "EN_REVISION_DOC", "prioridad": "NORMAL", "canalIngreso": "CORREO",
         "fechaIngreso": now_iso(-4),
         "monto": {"amountMicros": 25000000000, "currencyCode": "MXN"},
         "slaHoras": 24.0, "ubicacionTramite": "PROMOTORIA",
         "notasInternas": {"blocknote": "[]"},
         "agenteId": agente(0), "analistaAsignadoId": WS_MEMBER_ID, "gerenteRamoId": WS_MEMBER_ID},
    ]

    ids = []
    for t in tramites_data:
        result = gql("""
          mutation CreateTramite($data: TramiteCreateInput!) {
            createTramite(data: $data) { id folio }
          }
        """, {"data": t})
        node = result.get("createTramite")
        ids.append(ok(f"Trámite {t['folio']} ({t['estatus']})", node))
        time.sleep(0.25)
    return ids


def seed_historial_estatus(tramite_ids: list[str]) -> None:
    """Crea historial de cambios de estatus para los primeros 5 trámites."""
    print("\n► HistorialEstatus")
    if not tramite_ids or not tramite_ids[0]:
        print("  Sin IDs de trámites — omitiendo")
        return

    historiales = [
        # TRM-2026-001: RECIBIDO → EN_REVISION_DOC → DOCUMENTACION_COMPLETA
        {"tramiteId": tramite_ids[0], "entidadTipo": "TRAMITE", "entidadId": tramite_ids[0],
         "estatusAnterior": "RECIBIDO", "estatusNuevo": "EN_REVISION_DOC",
         "fechaCambio": now_iso(-7), "cambioAutomatico": False,
         "responsable": "Luis Gonzalez", "tiempoTranscurridoMinutos": 30.0,
         "motivoCambio": "Analista inicia revisión documental", "notas": ""},
        {"tramiteId": tramite_ids[0], "entidadTipo": "TRAMITE", "entidadId": tramite_ids[0],
         "estatusAnterior": "EN_REVISION_DOC", "estatusNuevo": "DOCUMENTACION_COMPLETA",
         "fechaCambio": now_iso(-6), "cambioAutomatico": False,
         "responsable": "Luis Gonzalez", "tiempoTranscurridoMinutos": 1440.0,
         "motivoCambio": "Documentación completa y validada", "notas": ""},

        # TRM-2026-002: RECIBIDO → EN_REVISION_DOC → DOCUMENTACION_COMPLETA → TURNADO_GNP → EN_PROCESO_GNP
        {"tramiteId": tramite_ids[1], "entidadTipo": "TRAMITE", "entidadId": tramite_ids[1],
         "estatusAnterior": "RECIBIDO", "estatusNuevo": "EN_REVISION_DOC",
         "fechaCambio": now_iso(-14), "cambioAutomatico": False,
         "responsable": "Luis Gonzalez", "tiempoTranscurridoMinutos": 60.0,
         "motivoCambio": "Inicio de revisión urgente por tipo SINIESTRO", "notas": ""},
        {"tramiteId": tramite_ids[1], "entidadTipo": "TRAMITE", "entidadId": tramite_ids[1],
         "estatusAnterior": "EN_REVISION_DOC", "estatusNuevo": "DOCUMENTACION_COMPLETA",
         "fechaCambio": now_iso(-13), "cambioAutomatico": False,
         "responsable": "Luis Gonzalez", "tiempoTranscurridoMinutos": 480.0,
         "motivoCambio": "Expediente completo para siniestro de fallecimiento", "notas": ""},
        {"tramiteId": tramite_ids[1], "entidadTipo": "TRAMITE", "entidadId": tramite_ids[1],
         "estatusAnterior": "DOCUMENTACION_COMPLETA", "estatusNuevo": "TURNADO_GNP",
         "fechaCambio": now_iso(-12), "cambioAutomatico": False,
         "responsable": "Luis Gonzalez", "tiempoTranscurridoMinutos": 120.0,
         "motivoCambio": "Subido a portal GNP. Folio: GNP-SIN-2026-4421", "notas": ""},
        {"tramiteId": tramite_ids[1], "entidadTipo": "TRAMITE", "entidadId": tramite_ids[1],
         "estatusAnterior": "TURNADO_GNP", "estatusNuevo": "EN_PROCESO_GNP",
         "fechaCambio": now_iso(-10), "cambioAutomatico": True,
         "responsable": "Sistema", "tiempoTranscurridoMinutos": 2880.0,
         "motivoCambio": "Confirmación de recepción por GNP", "notas": ""},

        # TRM-2026-003: llegó hasta DETENIDO
        {"tramiteId": tramite_ids[2], "entidadTipo": "TRAMITE", "entidadId": tramite_ids[2],
         "estatusAnterior": "EN_PROCESO_GNP", "estatusNuevo": "DETENIDO",
         "fechaCambio": now_iso(-15), "cambioAutomatico": False,
         "responsable": "Luis Gonzalez", "tiempoTranscurridoMinutos": 4320.0,
         "motivoCambio": "GNP solicita acta de nacimiento actualizada del beneficiario",
         "notas": "Suscriptor GNP: María Gutiérrez"},
    ]

    for h in historiales:
        result = gql("""
          mutation CreateHistorialEstatus($data: HistorialEstatusCreateInput!) {
            createHistorialEstatus(data: $data) { id }
          }
        """, {"data": h})
        node = result.get("createHistorialEstatus")
        label = f"{h['estatusAnterior']} → {h['estatusNuevo']}"
        ok(f"Historial [{label}] tramite #{tramite_ids.index(h['tramiteId'])+1}", node)
        time.sleep(0.2)


def seed_hilos_conversacion(tramite_ids: list[str], agente_ids: list[str]) -> None:
    """Crea hilos de conversación vinculados a trámites."""
    print("\n► HilosConversacion")
    if not tramite_ids or not agente_ids:
        print("  Sin IDs — omitiendo")
        return

    def ag(i): return agente_ids[i % len(agente_ids)] if agente_ids[i % len(agente_ids)] else None

    hilos = [
        {"name": "Re: Solicitud emisión póliza vida TRM-2026-001",
         "asunto": "Re: Solicitud emisión póliza vida TRM-2026-001",
         "threadExternalId": "gmail_thread_aabbcc112233",
         "canalOrigen": "CORREO", "estatusHilo": "ACTIVO",
         "ultimoMensajeEn": now_iso(-6), "mensajesCount": 5.0,
         "ultimoRemitente": "AGENTE", "requiereAccion": False,
         "tramiteId": tramite_ids[0], "agenteId": ag(0)},
        {"name": "URGENTE: Siniestro fallecimiento - TRM-2026-002",
         "asunto": "URGENTE: Siniestro fallecimiento - TRM-2026-002",
         "threadExternalId": "gmail_thread_ccddee334455",
         "canalOrigen": "CORREO", "estatusHilo": "ACTIVO",
         "ultimoMensajeEn": now_iso(-3), "mensajesCount": 8.0,
         "ultimoRemitente": "ANALISTA", "requiereAccion": True,
         "tramiteId": tramite_ids[1], "agenteId": ag(0)},
        {"name": "Nuevo trámite GMM - TRM-2026-004",
         "asunto": "Nuevo trámite GMM - TRM-2026-004",
         "threadExternalId": "gmail_thread_eeffgg556677",
         "canalOrigen": "CORREO", "estatusHilo": "ACTIVO",
         "ultimoMensajeEn": now_iso(-1), "mensajesCount": 2.0,
         "ultimoRemitente": "AGENTE", "requiereAccion": False,
         "tramiteId": tramite_ids[3], "agenteId": ag(1)},
        {"name": "Consulta sin tramite - documentos Autos",
         "asunto": "Consulta: ¿qué documentos necesitan para el seguro de auto?",
         "threadExternalId": "gmail_thread_hhiijj778899",
         "canalOrigen": "CORREO", "estatusHilo": "ESPERANDO_RESPUESTA",
         "ultimoMensajeEn": now_iso(-5), "mensajesCount": 1.0,
         "ultimoRemitente": "AGENTE", "requiereAccion": True,
         "tramiteId": None, "agenteId": ag(3)},
    ]

    for h in hilos:
        # Remove None values
        hilo_data = {k: v for k, v in h.items() if v is not None}
        result = gql("""
          mutation CreateHiloConversacion($data: HiloConversacionCreateInput!) {
            createHiloConversacion(data: $data) { id }
          }
        """, {"data": hilo_data})
        node = result.get("createHiloConversacion")
        ok(f"Hilo: {h['asunto'][:60]}", node)
        time.sleep(0.2)


def seed_alertas(tramite_ids: list[str]) -> None:
    """Crea alertas enviadas para algunos trámites."""
    print("\n► AlertasTramite")
    if len(tramite_ids) < 3:
        print("  Insuficientes IDs — omitiendo")
        return

    alertas = [
        {"name": "Alerta: Documentación incompleta TRM-2026-004",
         "tipoAlerta": "DOCUMENTACION_INCOMPLETA", "canal": "EMAIL",
         "fechaEnvio": now_iso(-1), "respondido": False,
         "mensaje": {"blocknote": "[]"},
         "tramiteId": tramite_ids[3]},
        {"name": "Alerta: Trámite detenido TRM-2026-003",
         "tipoAlerta": "TRAMITE_DETENIDO", "canal": "WHATSAPP",
         "fechaEnvio": now_iso(-14), "respondido": True,
         "mensaje": {"blocknote": "[]"},
         "tramiteId": tramite_ids[2]},
        {"name": "Alerta: Resolución disponible TRM-2026-006",
         "tipoAlerta": "RESOLUCION_DISPONIBLE", "canal": "EMAIL",
         "fechaEnvio": now_iso(-20), "respondido": True,
         "mensaje": {"blocknote": "[]"},
         "tramiteId": tramite_ids[5]},
        {"name": "Recordatorio: Siniestro pendiente TRM-2026-008",
         "tipoAlerta": "RECORDATORIO", "canal": "WHATSAPP",
         "fechaEnvio": now_iso(-2), "respondido": False,
         "mensaje": {"blocknote": "[]"},
         "tramiteId": tramite_ids[7]},
    ]

    for a in alertas:
        result = gql("""
          mutation CreateAlertaTramite($data: AlertaTramiteCreateInput!) {
            createAlertaTramite(data: $data) { id }
          }
        """, {"data": a})
        node = result.get("createAlertaTramite")
        ok(f"Alerta {a['tipoAlerta']} tramite #{tramite_ids.index(a['tramiteId'])+1}", node)
        time.sleep(0.2)


# ── Supabase seed ──────────────────────────────────────────────────────────────

def seed_supabase_incoming_emails(tramite_ids: list[str]) -> list[str]:
    """Ingesta correos entrantes simulados."""
    print("\n  Supabase: incoming_emails")
    # Only columns that exist in the table:
    # id, gmail_message_id, gmail_thread_id, sender_email, sender_name,
    # subject, body_text, body_html, received_at, attachment_count,
    # processing_status, error_message, tramite_twenty_id, created_at, updated_at
    emails = [
        {"gmail_message_id": "msg_aabb001", "gmail_thread_id": "thread_aabb001",
         "sender_email": "roberto.mendez@correo.mx", "sender_name": "Roberto Mendez",
         "subject": "Solicitud emisión póliza vida - Roberto Medina",
         "body_text": "Buenos días, adjunto la documentación para la emisión de la póliza de vida.",
         "received_at": now_iso(-8), "attachment_count": 5,
         "processing_status": "linked", "tramite_twenty_id": tramite_ids[0] if tramite_ids else None},
        {"gmail_message_id": "msg_ccdd002", "gmail_thread_id": "thread_ccdd002",
         "sender_email": "carmen.reyes@seguros.mx", "sender_name": "Carmen Reyes",
         "subject": "URGENTE: Siniestro fallecimiento Sr. Pérez - póliza V-GNP-2020-1234",
         "body_text": "Se reporta fallecimiento del asegurado. Adjunto acta de defunción y demás documentos.",
         "received_at": now_iso(-15), "attachment_count": 7,
         "processing_status": "linked", "tramite_twenty_id": tramite_ids[1] if len(tramite_ids) > 1 else None},
        {"gmail_message_id": "msg_eeff003", "gmail_thread_id": "thread_eeff003",
         "sender_email": "despacho@aztecaseguros.mx", "sender_name": "Distribuidora Azteca",
         "subject": "Nuevo trámite GMM grupal - Empresa Comercial ABC",
         "body_text": "Estimados, enviamos la solicitud de GMM grupal para Comercial ABC, 45 vidas.",
         "received_at": now_iso(-1), "attachment_count": 3,
         "processing_status": "ready_for_tramite", "tramite_twenty_id": None},
        {"gmail_message_id": "msg_gghh004", "gmail_thread_id": "thread_gghh004",
         "sender_email": "jorge.salinas@correo.mx", "sender_name": "Jorge Salinas",
         "subject": "Endoso cambio de datos - Toyota Camry 2022",
         "body_text": "Solicito endoso de cambio de domicilio del vehículo. Adjunto comprobante.",
         "received_at": now_iso(-3), "attachment_count": 2,
         "processing_status": "linked", "tramite_twenty_id": tramite_ids[6] if len(tramite_ids) > 6 else None},
        {"gmail_message_id": "msg_iijj005", "gmail_thread_id": "thread_iijj005",
         "sender_email": "patricia.torres@agentegnp.mx", "sender_name": "Patricia Torres",
         "subject": "Cotización seguros pyme - Restaurante El Buen Sabor",
         "body_text": "Buenos días, me solicitan una cotización para asegurar un restaurante.",
         "received_at": now_iso(-7), "attachment_count": 1,
         "processing_status": "linked", "tramite_twenty_id": tramite_ids[9] if len(tramite_ids) > 9 else None},
        {"gmail_message_id": "msg_kkll006", "gmail_thread_id": "thread_kkll006",
         "sender_email": "asistente@aztecaseguros.mx", "sender_name": "Sandra Vela",
         "subject": "Pregunta sobre documentos para seguro de vida",
         "body_text": "¿Cuáles son los documentos necesarios para una póliza de vida individual?",
         "received_at": now_iso(-5), "attachment_count": 0,
         "processing_status": "received", "tramite_twenty_id": None},
        {"gmail_message_id": "msg_mmnn007", "gmail_thread_id": "thread_mmnn007",
         "sender_email": "roberto.mendez@correo.mx", "sender_name": "Roberto Mendez",
         "subject": "Re: Seguimiento siniestro TRM-2026-002",
         "body_text": "¿Hay alguna novedad del siniestro? Ya pasaron 10 días.",
         "received_at": now_iso(-5), "attachment_count": 0,
         "processing_status": "linked", "tramite_twenty_id": tramite_ids[1] if len(tramite_ids) > 1 else None},
    ]

    result = supabase_insert("incoming_emails", emails)
    print(f"  → {len(result)} incoming_emails insertados")
    return [r.get("id", "") for r in result]


def seed_supabase_tramites_pipeline(agente_cuas: list[str], tramite_twenty_ids: list[str]) -> list[str]:
    """Crea registros en tramites_pipeline (espejo del procesamiento IA)."""
    print("\n  Supabase: tramites_pipeline")
    tramites = []
    folios = [f"TRM-2026-{str(i).zfill(3)}" for i in range(1, 11)]

    configs = [
        ("roberto.mendez@correo.mx", "Roberto Mendez Vega", "GNP-001-MX", "VIDA", "EMISION",
         "completado", tramite_twenty_ids[0] if tramite_twenty_ids else None, folios[0]),
        ("carmen.reyes@seguros.mx", "Carmen Reyes Fuentes", "GNP-002-MX", "GMM", "SINIESTRO",
         "completado", tramite_twenty_ids[1] if len(tramite_twenty_ids) > 1 else None, folios[1]),
        ("despacho@aztecaseguros.mx", "Distribuidora Azteca", "GNP-003-MX", "PYME", "EMISION",
         "completado", tramite_twenty_ids[2] if len(tramite_twenty_ids) > 2 else None, folios[2]),
        ("carmen.reyes@seguros.mx", "Carmen Reyes Fuentes", "GNP-002-MX", "GMM", "EMISION",
         "completado", tramite_twenty_ids[3] if len(tramite_twenty_ids) > 3 else None, folios[3]),
        ("carmen.reyes@seguros.mx", "Carmen Reyes Fuentes", "GNP-002-MX", "GMM", "RENOVACION",
         "completado", tramite_twenty_ids[4] if len(tramite_twenty_ids) > 4 else None, folios[4]),
        ("carmen.reyes@seguros.mx", "Carmen Reyes Fuentes", "GNP-002-MX", "GMM", "EMISION",
         "completado", tramite_twenty_ids[5] if len(tramite_twenty_ids) > 5 else None, folios[5]),
        ("jorge.salinas@correo.mx", "Jorge Salinas Montoya", "GNP-004-MX", "AUTOS", "EMISION",
         "procesando", tramite_twenty_ids[6] if len(tramite_twenty_ids) > 6 else None, folios[6]),
        ("jorge.salinas@correo.mx", "Jorge Salinas Montoya", "GNP-004-MX", "AUTOS", "SINIESTRO",
         "completado", tramite_twenty_ids[7] if len(tramite_twenty_ids) > 7 else None, folios[7]),
        ("patricia.torres@agentegnp.mx", "Patricia Torres Luna", "GNP-005-MX", "PYME", "EMISION",
         "completado", tramite_twenty_ids[9] if len(tramite_twenty_ids) > 9 else None, folios[9]),
        ("roberto.mendez@correo.mx", "Roberto Mendez Vega", "GNP-001-MX", "GMM", "EMISION",
         "procesando", tramite_twenty_ids[14] if len(tramite_twenty_ids) > 14 else None, "TRM-2026-015"),
    ]

    for correo, nombre, cua, ramo, tipo, estado, twenty_id, folio in configs:
        tramites.append({
            "folio": folio,
            "ramo": ramo,
            "tipo_tramite": tipo,
            "status": estado,
            "canal_ingreso": "Correo",
            "nombre_agente": nombre,
            "email_agente": correo,
            "clave_agente": cua,
            "prioridad": "Normal",
            "resumen_ia": f"Trámite de {tipo.lower()} ramo {ramo} del agente {nombre}",
            "accion_requerida": "Revisión documental" if estado == "procesando" else None,
            "twenty_tramite_id": twenty_id,
            "confianza_global": 92,
            "es_duplicado_posible": False,
            "tiene_adjuntos": True,
        })

    result = supabase_insert("tramites_pipeline", tramites)
    print(f"  → {len(result)} tramites_pipeline insertados")
    return [r.get("id", "") for r in result]


def seed_supabase_attachments_log(pipeline_ids: list[str]) -> None:
    """Crea registros de documentos procesados por Agente 3."""
    print("\n  Supabase: attachments_log")
    if not pipeline_ids:
        print("  Sin pipeline_ids — omitiendo")
        return

    docs = []
    doc_types = [
        ("INE", "INE del contratante", True),
        ("SOL_GNP", "Solicitud de seguro firmada", True),
        ("COMP_DOM", "Comprobante de domicilio", True),
        ("COMP_PAGO", "Comprobante de primer pago", False),
        ("ACTA_NAC", "Acta de nacimiento asegurado", True),
    ]

    for i, pid in enumerate(pipeline_ids[:5]):
        if not pid:
            continue
        for j, (tipo, nombre, validado) in enumerate(doc_types):
            # Actual columns: id, email_id, bucket_id, total_attachments, successful_attachments,
            # file_paths, es_inline, mime_type, tipo_documento, texto_extraido, datos_extraidos,
            # metodo_extraccion, ocr_completado, clasificacion_completada, twenty_documento_id,
            # error_detalle, procesado_at, created_at
            docs.append({
                "email_id": f"msg_aabb00{i+1}",
                "bucket_id": "tramite-docs",
                "total_attachments": len(doc_types),
                "successful_attachments": sum(1 for _, _, v in doc_types if v),
                "file_paths": [f"tramite-docs/TRM-2026-{str(i+1).zfill(3)}/{tipo}/documento_{j+1}.pdf"],
                "mime_type": "application/pdf",
                "tipo_documento": tipo,
                "texto_extraido": f"Texto extraído del documento {nombre}..." if validado else None,
                "datos_extraidos": {"nombre": nombre, "tipo": tipo} if validado else None,
                "metodo_extraccion": "ocr" if validado else None,
                "ocr_completado": validado,
                "clasificacion_completada": True,
                "es_inline": False,
                "procesado_at": now_iso(-(i + 1)),
            })

    result = supabase_insert("attachments_log", docs)
    print(f"  → {len(result)} attachments_log insertados")


def seed_supabase_historial_estatus(tramite_pipeline_ids: list[str], tramite_twenty_ids: list[str]) -> None:
    """Crea historial de estatus en Supabase (auditoría para analytics)."""
    print("\n  Supabase: historial_estatus")
    registros = []
    if not tramite_pipeline_ids:
        return

    # TRM-2026-001: secuencia completa
    if len(tramite_pipeline_ids) > 0 and tramite_pipeline_ids[0]:
        for prev, nuevo, delta_dias, dur in [
            ("procesando", "RECIBIDO", -8, 30),
            ("RECIBIDO", "EN_REVISION_DOC", -7, 30),
            ("EN_REVISION_DOC", "DOCUMENTACION_COMPLETA", -6, 1440),
        ]:
            registros.append({
                "tramite_pipeline_id": tramite_pipeline_ids[0],
                "twenty_tramite_id": tramite_twenty_ids[0] if tramite_twenty_ids else None,
                "estatus_anterior": prev,
                "estatus_nuevo": nuevo,
                "fecha_cambio": now_iso(delta_dias),
                "actor": "analista",
                "duracion_en_estatus_horas": round(dur / 60, 2),
                "fuente": "crm_manual",
            })

    # TRM-2026-002: hasta DETENIDO
    if len(tramite_pipeline_ids) > 1 and tramite_pipeline_ids[1]:
        for prev, nuevo, delta_dias, dur in [
            ("RECIBIDO", "EN_REVISION_DOC", -14, 60),
            ("EN_REVISION_DOC", "DOCUMENTACION_COMPLETA", -13, 480),
            ("DOCUMENTACION_COMPLETA", "TURNADO_GNP", -12, 120),
            ("TURNADO_GNP", "EN_PROCESO_GNP", -10, 2880),
        ]:
            registros.append({
                "tramite_pipeline_id": tramite_pipeline_ids[1],
                "twenty_tramite_id": tramite_twenty_ids[1] if len(tramite_twenty_ids) > 1 else None,
                "estatus_anterior": prev,
                "estatus_nuevo": nuevo,
                "fecha_cambio": now_iso(delta_dias),
                "actor": "analista" if "automatico" not in prev else "sistema",
                "duracion_en_estatus_horas": round(dur / 60, 2),
                "fuente": "pipeline",
            })

    result = supabase_insert("historial_estatus", registros)
    print(f"  → {len(result)} historial_estatus insertados")


def seed_supabase_notas_interacciones(tramite_twenty_ids: list[str], agente_cuas: list[str]) -> None:
    """Crea notas e interacciones en Supabase."""
    print("\n  Supabase: notas_interacciones")
    notas = [
        {"entidad_tipo": "tramite", "entidad_twenty_id": tramite_twenty_ids[0] if tramite_twenty_ids else "n/a",
         "tipo": "Email", "canal_origen": "CORREO",
         "asunto": "Solicitud emisión póliza vida",
         "contenido": "Estimados, adjunto los documentos para la emisión. Quedo al pendiente.",
         "resumen_ia": "Agente envía documentación completa para trámite de emisión de vida. Tono neutral.",
         "sentimiento": "Neutro", "hilo_id": "thread_aabb001",
         "gmail_message_id": "msg_aabb001",
         "autor_email": "roberto.mendez@correo.mx", "urgencia_detectada": False,
         "etiquetas": ["documentacion", "emision", "vida"]},
        {"entidad_tipo": "tramite", "entidad_twenty_id": tramite_twenty_ids[1] if len(tramite_twenty_ids) > 1 else "n/a",
         "tipo": "Email", "canal_origen": "CORREO",
         "asunto": "URGENTE: Siniestro fallecimiento",
         "contenido": "Es URGENTE, mi cliente falleció ayer. Necesito que procesen el siniestro de inmediato.",
         "resumen_ia": "Agente reporta fallecimiento de asegurado con tono muy urgente. Requiere atención inmediata.",
         "sentimiento": "Negativo", "hilo_id": "thread_ccdd002",
         "gmail_message_id": "msg_ccdd002",
         "autor_email": "carmen.reyes@seguros.mx", "urgencia_detectada": True,
         "etiquetas": ["urgente", "siniestro", "fallecimiento"]},
        {"entidad_tipo": "tramite", "entidad_twenty_id": tramite_twenty_ids[1] if len(tramite_twenty_ids) > 1 else "n/a",
         "tipo": "Nota_Interna", "canal_origen": "MANUAL",
         "asunto": "Nota analista: contacto GNP",
         "contenido": "Hablé con María Gutiérrez de GNP. Solicitan acta de defunción y formato especial de beneficiarios.",
         "resumen_ia": "Analista documenta requerimientos adicionales de GNP para siniestro de fallecimiento.",
         "sentimiento": "Neutro", "hilo_id": None,
         "autor_email": "lag.diazdeleon@gmail.com", "urgencia_detectada": False,
         "etiquetas": ["gnp", "requisito", "siniestro"]},
        {"entidad_tipo": "agente", "entidad_twenty_id": "agente_placeholder",
         "tipo": "Llamada", "canal_origen": "MANUAL",
         "asunto": "Seguimiento detenido TRM-2026-003",
         "contenido": "Llamé a Roberto para informarle del endoso detenido. Comprende y enviará el acta actualizada.",
         "resumen_ia": "Analista notifica a agente sobre detención de endoso. Agente responde positivamente.",
         "sentimiento": "Positivo", "hilo_id": None,
         "autor_email": "lag.diazdeleon@gmail.com", "urgencia_detectada": False,
         "etiquetas": ["detenido", "endoso", "llamada"]},
        {"entidad_tipo": "tramite", "entidad_twenty_id": tramite_twenty_ids[7] if len(tramite_twenty_ids) > 7 else "n/a",
         "tipo": "Email", "canal_origen": "CORREO",
         "asunto": "¿Cuándo resuelven el siniestro del auto?",
         "contenido": "Ya pasaron 2 semanas. Necesito saber cuándo GNP va a pagar el siniestro.",
         "resumen_ia": "Agente expresa frustración por la demora en resolución del siniestro de auto.",
         "sentimiento": "Negativo", "hilo_id": "thread_eeff007",
         "autor_email": "jorge.salinas@correo.mx", "urgencia_detectada": True,
         "etiquetas": ["siniestro", "queja", "demora", "autos"]},
    ]

    # Reemplazar placeholder si hay agente IDs
    result = supabase_insert("notas_interacciones", notas)
    print(f"  → {len(result)} notas_interacciones insertadas")


def seed_supabase_cobertura_analistas() -> None:
    """Crea coberturas vacacionales de analistas."""
    print("\n  Supabase: cobertura_analistas")
    coberturas = [
        {"analista_twenty_id": WS_MEMBER_ID,
         "sustituto_twenty_id": WS_MEMBER_ID,
         "ramo": "VIDA",
         "fecha_inicio": date_iso(5),
         "fecha_fin": date_iso(15),
         "activo": True,
         "creado_por": "Luis Gonzalez"},
        {"analista_twenty_id": WS_MEMBER_ID,
         "sustituto_twenty_id": WS_MEMBER_ID,
         "ramo": "GMM",
         "fecha_inicio": date_iso(10),
         "fecha_fin": date_iso(20),
         "activo": True,
         "creado_por": "Luis Gonzalez"},
    ]
    result = supabase_insert("cobertura_analistas", coberturas)
    print(f"  → {len(result)} cobertura_analistas insertadas")


def seed_supabase_historial_asignaciones(pipeline_ids: list[str], tramite_twenty_ids: list[str]) -> None:
    """Log de asignaciones automáticas."""
    print("\n  Supabase: historial_asignaciones")
    asignaciones = []
    for i, (pid, tid) in enumerate(zip(pipeline_ids[:6], tramite_twenty_ids[:6])):
        if pid:
            asignaciones.append({
                "tramite_pipeline_id": pid,
                "twenty_tramite_id": tid if tid else None,
                "analista_twenty_id": WS_MEMBER_ID,
                "agente_twenty_id": None,
                "tipo_asignacion": "automatica" if i < 4 else "manual",
                "motivo": "Asignación automática por ramo" if i < 4 else "Reasignación manual por gerente",
                "asignado_por": "sistema" if i < 4 else "Luis Gonzalez",
                "ramo": ["VIDA", "GMM", "PYME", "GMM", "AUTOS", "AUTOS"][i],
            })
    result = supabase_insert("historial_asignaciones", asignaciones)
    print(f"  → {len(result)} historial_asignaciones insertadas")


def seed_supabase_agent_performance() -> None:
    """Crea snapshots de desempeño mensual por agente."""
    print("\n  Supabase: agent_performance_monthly")
    mes_actual = date.today().strftime("%m-%Y")
    performances = [
        {"agente_cua": "GNP-001-MX", "mes_anio": mes_actual,
         "tramites_totales": 12, "tramites_resueltos": 10, "tramites_rechazados": 1, "tramites_cancelados": 0,
         "first_pass_yield": 91.67, "promedio_docs_faltantes": 0.5,
         "prima_emitida": 185000.00, "bono_proyectado": 9250.00,
         "tasa_cumplimiento_sla": 95.0, "tramites_vencidos_sla": 1,
         "tiempo_promedio_resolucion_horas": 38.5, "es_vigente": True,
         "desglose_ramo": {"VIDA": {"total": 8, "resueltos": 7}, "GMM": {"total": 4, "resueltos": 3}}},
        {"agente_cua": "GNP-002-MX", "mes_anio": mes_actual,
         "tramites_totales": 8, "tramites_resueltos": 7, "tramites_rechazados": 0, "tramites_cancelados": 0,
         "first_pass_yield": 100.0, "promedio_docs_faltantes": 0.2,
         "prima_emitida": 142000.00, "bono_proyectado": 7100.00,
         "tasa_cumplimiento_sla": 100.0, "tramites_vencidos_sla": 0,
         "tiempo_promedio_resolucion_horas": 21.0, "es_vigente": True,
         "desglose_ramo": {"GMM": {"total": 5, "resueltos": 5}, "AUTOS": {"total": 3, "resueltos": 2}}},
        {"agente_cua": "GNP-003-MX", "mes_anio": mes_actual,
         "tramites_totales": 5, "tramites_resueltos": 3, "tramites_rechazados": 1, "tramites_cancelados": 1,
         "first_pass_yield": 66.67, "promedio_docs_faltantes": 1.8,
         "prima_emitida": 95000.00, "bono_proyectado": 2375.00,
         "tasa_cumplimiento_sla": 60.0, "tramites_vencidos_sla": 2,
         "tiempo_promedio_resolucion_horas": 52.0, "es_vigente": True,
         "desglose_ramo": {"PYME": {"total": 3, "resueltos": 2}, "DANOS": {"total": 2, "resueltos": 1}}},
        {"agente_cua": "GNP-004-MX", "mes_anio": mes_actual,
         "tramites_totales": 6, "tramites_resueltos": 4, "tramites_rechazados": 1, "tramites_cancelados": 0,
         "first_pass_yield": 80.0, "promedio_docs_faltantes": 0.8,
         "prima_emitida": 67500.00, "bono_proyectado": 1687.50,
         "tasa_cumplimiento_sla": 83.33, "tramites_vencidos_sla": 1,
         "tiempo_promedio_resolucion_horas": 29.5, "es_vigente": True,
         "desglose_ramo": {"AUTOS": {"total": 6, "resueltos": 4}}},
        {"agente_cua": "GNP-005-MX", "mes_anio": mes_actual,
         "tramites_totales": 15, "tramites_resueltos": 13, "tramites_rechazados": 0, "tramites_cancelados": 1,
         "first_pass_yield": 93.33, "promedio_docs_faltantes": 0.1,
         "prima_emitida": 312000.00, "bono_proyectado": 23400.00,
         "tasa_cumplimiento_sla": 93.33, "tramites_vencidos_sla": 1,
         "tiempo_promedio_resolucion_horas": 33.0, "es_vigente": True,
         "desglose_ramo": {"VIDA": {"total": 5, "resueltos": 5}, "GMM": {"total": 4, "resueltos": 4}, "DANOS": {"total": 6, "resueltos": 4}}},
    ]
    result = supabase_insert("agent_performance_monthly", performances)
    print(f"  → {len(result)} agent_performance_monthly insertados")


def seed_supabase_kpi_snapshots() -> None:
    """Crea snapshots de KPIs globales."""
    print("\n  Supabase: kpi_snapshots_cache")
    mes_actual = date.today().strftime("%m-%Y")
    hoy = date.today()
    inicio_mes = date(hoy.year, hoy.month, 1)
    fin_mes = date(hoy.year, hoy.month + 1, 1) - timedelta(days=1) if hoy.month < 12 else date(hoy.year, 12, 31)

    snapshots = [
        {"periodo_inicio": inicio_mes.isoformat(), "periodo_fin": fin_mes.isoformat(),
         "granularidad": "MENSUAL",
         "total_tramites": 46, "tramites_resueltos": 37, "tramites_pendientes": 7,
         "tramites_vencidos_sla": 5, "tramites_en_riesgo_sla": 3,
         "tiempo_promedio_horas": 34.2,
         "tasa_auto_matching_pct": 88.5, "tasa_exito_ocr_pct": 94.3,
         "tasa_primera_vez_pct": 87.0,
         "desglose_ramo": {
             "VIDA": {"total": 15, "resueltos": 12, "vencidos": 1},
             "GMM": {"total": 17, "resueltos": 14, "vencidos": 2},
             "AUTOS": {"total": 9, "resueltos": 7, "vencidos": 1},
             "PYME": {"total": 3, "resueltos": 2, "vencidos": 1},
             "DANOS": {"total": 2, "resueltos": 2, "vencidos": 0},
         },
         "desglose_estatus": {
             "RECIBIDO": 3, "EN_REVISION_DOC": 2, "DOCUMENTACION_COMPLETA": 2,
             "TURNADO_GNP": 3, "EN_PROCESO_GNP": 4, "DETENIDO": 2, "RESUELTO": 28, "CANCELADO": 2,
         },
         "metricas_json": {
             "SLA_Compliance_Global": 89.1,
             "First_Pass_Yield": 87.0,
             "Alertas_Cedula_60dias": 2,
             "Prima_Emitida_MXN": 801500,
         },
         "es_vigente": True,
         "calculado_at": now_iso()},
    ]
    result = supabase_insert("kpi_snapshots_cache", snapshots)
    print(f"  → {len(result)} kpi_snapshots_cache insertados")


def seed_supabase_pipeline_logs(pipeline_ids: list[str]) -> None:
    """Crea logs del pipeline para debug."""
    print("\n  Supabase: pipeline_logs")
    logs = []
    etapas = ["agente1", "adjuntos", "agente3", "agente4", "acuse"]
    for i, pid in enumerate(pipeline_ids[:5]):
        if not pid:
            continue
        for etapa in etapas[:3]:
            logs.append({
                "tramite_id": pid,
                "etapa": etapa,
                "nivel": "info",
                "error_message": None,
                "contexto": {"email_id": f"msg_aabb00{i+1}", "duracion_ms": 1200 + i * 100},
            })
        # Un error simulado en el tercer trámite
        if i == 2:
            logs.append({
                "tramite_id": pid,
                "etapa": "agente3",
                "nivel": "warning",
                "error_message": "PDF encriptado: requirió desencriptación manual",
                "contexto": {"archivo": "solicitud_firmada.pdf", "intento": 2},
            })

    result = supabase_insert("pipeline_logs", logs)
    print(f"  → {len(result)} pipeline_logs insertados")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*65}")
    print("  Seed de Datos de Prueba — Promotoría GNP")
    print(f"  Twenty CRM: {TWENTY_URL}")
    print(f"  Supabase: {SUPABASE_URL}")
    print(f"{'='*65}\n")

    # ── Twenty CRM ─────────────────────────────────────────────────────────────
    print("\n◆ TWENTY CRM")

    producto_ids = seed_productos()
    agente_ids   = seed_agentes()
    seed_colaboradores(agente_ids)
    tramite_ids  = seed_tramites(agente_ids)
    seed_historial_estatus(tramite_ids)
    seed_hilos_conversacion(tramite_ids, agente_ids)
    seed_alertas(tramite_ids)

    # ── Supabase ────────────────────────────────────────────────────────────────
    print("\n◆ SUPABASE")

    agente_cuas = ["GNP-001-MX", "GNP-002-MX", "GNP-003-MX", "GNP-004-MX", "GNP-005-MX"]
    seed_supabase_incoming_emails(tramite_ids)
    pipeline_ids = seed_supabase_tramites_pipeline(agente_cuas, tramite_ids)
    seed_supabase_attachments_log(pipeline_ids)
    seed_supabase_historial_estatus(pipeline_ids, tramite_ids)
    seed_supabase_notas_interacciones(tramite_ids, agente_cuas)
    seed_supabase_cobertura_analistas()
    seed_supabase_historial_asignaciones(pipeline_ids, tramite_ids)
    seed_supabase_agent_performance()
    seed_supabase_kpi_snapshots()
    seed_supabase_pipeline_logs(pipeline_ids)

    print(f"\n{'='*65}")
    print("  ✓ Seed completado")
    print(f"    Twenty: {len([i for i in producto_ids if i])} productos, "
          f"{len([i for i in agente_ids if i])} agentes, "
          f"{len([i for i in tramite_ids if i])} trámites")
    print(f"    Supabase: {len([i for i in pipeline_ids if i])} registros pipeline")
    print(f"{'='*65}\n")
    print("Verificación rápida:")
    print("  Twenty → http://localhost:3000/objects/agentes")
    print("  Twenty → http://localhost:3000/objects/tramites")
    print("  Supabase → Table Editor → tramites_pipeline, incoming_emails")


if __name__ == "__main__":
    main()
