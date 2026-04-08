"""
setup_twenty_objects.py
Configura el modelo de datos completo de la promotoría en Twenty CRM via Metadata API.

Capa I — Identidad y Jerarquía:
  - agente               → Agente externo GNP (CUA, RFC, cédula CNSF, ramos, GD asignado)
  - colaborador          → Sub-agente bajo un CUA principal (RFC, CURP, rol, porcentaje participación)
  - asegurado            → Cliente final asegurado (CURP, RFC, género, estado civil)
  - workspaceMember      → Equipo interno (rol, ramo de especialidad, meta mensual)

Capa II — Operativa (Trámites y Flujo):
  - producto             → Catálogo de productos de seguros GNP
  - tramite              → Objeto central (folio, estatus, SLA, ubicación balón, producto)
  - historialEstatus     → Auditoría de cambios de estatus por tramite
  - documentoTramite     → Checklist documental con metadatos OCR y hash de integridad
  - alertaTramite        → Notificaciones enviadas al agente
  - notaInteraccion      → Emails, WhatsApp, llamadas, notas internas con resumen IA
  - gnpPortalMirror      → Espejo del estado oficial en el portal de GNP
  - hiloConversacion     → Hilo de conversación email/WhatsApp vinculado a tramite

Capa III — Analítica y KPIs:
  - kpiSnapshot          → Métricas globales para directivos (SLA, volumen, tasa éxito)
  - agentPerformanceMonthly → Desempeño mensual por agente (FPY, prima, bono)

El script es idempotente: re-ejecutar no duplica objetos ni campos.

Uso:
  python3 scripts/setup_twenty_objects.py
"""

import json
import os
import sys
import time
import uuid
from pathlib import Path
import urllib.request
import urllib.error

# ── Configuración ──────────────────────────────────────────────────────────────

# Lee desde .env si existe
env_path = Path(__file__).parent.parent / "packages/twenty-docker/.env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

API_KEY = os.environ.get("TWENTY_API_KEY", "")
BASE_URL = os.environ.get("TWENTY_API_URL", "http://localhost:3000")
METADATA_URL = f"{BASE_URL}/metadata"

if not API_KEY:
    print("ERROR: TWENTY_API_KEY no encontrado en .env")
    sys.exit(1)

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}",
}


# ── GraphQL helper ─────────────────────────────────────────────────────────────

def gql(query: str, variables: dict = None) -> dict:
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    body = json.dumps(payload).encode()
    req = urllib.request.Request(METADATA_URL, data=body, headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        print(f"  HTTP {e.code}: {body_text[:300]}")
        return {}
    if "errors" in data:
        for err in data["errors"]:
            print(f"  GQL Error: {err.get('message')}")
        return {}
    return data.get("data", {})


# ── Helpers ────────────────────────────────────────────────────────────────────

def get_existing_objects() -> dict:
    """Retorna {nameSingular: id} de todos los objetos existentes (hasta 100 via cursor paging)."""
    result = gql('{ objects(paging: {first: 100}) { edges { node { id nameSingular } } } }')
    edges = result.get("objects", {}).get("edges", [])
    return {e["node"]["nameSingular"]: e["node"]["id"] for e in edges}


def get_existing_fields(object_id: str) -> set:
    """Retorna el set de nombres de campos ya existentes en un objeto (hasta 200)."""
    result = gql(
        """
        query GetFields($filter: FieldFilter) {
          fields(filter: $filter, paging: {first: 200}) { edges { node { name } } }
        }
        """,
        {"filter": {"objectMetadataId": {"eq": object_id}}},
    )
    edges = result.get("fields", {}).get("edges", [])
    return {e["node"]["name"] for e in edges}


def create_object(name_singular: str, name_plural: str, label_singular: str,
                  label_plural: str, description: str, icon: str) -> str | None:
    result = gql(
        """
        mutation CreateObject($input: CreateOneObjectInput!) {
          createOneObject(input: $input) { id nameSingular }
        }
        """,
        {
            "input": {
                "object": {
                    "nameSingular": name_singular,
                    "namePlural": name_plural,
                    "labelSingular": label_singular,
                    "labelPlural": label_plural,
                    "description": description,
                    "icon": icon,
                }
            }
        },
    )
    obj = result.get("createOneObject")
    if obj:
        print(f"  ✓ Objeto '{name_singular}' creado (id={obj['id']})")
        return obj["id"]
    return None


def create_field(object_id: str, field_type: str, name: str, label: str,
                 description: str = "", icon: str = "IconTag",
                 options: list = None, is_nullable: bool = True,
                 default_value=None, settings: dict = None,
                 existing: set = None) -> bool:
    if existing and name in existing:
        print(f"    — Campo '{name}' ya existe, omitiendo")
        return True

    field_input = {
        "objectMetadataId": object_id,
        "type": field_type,
        "name": name,
        "label": label,
        "description": description,
        "icon": icon,
        "isNullable": is_nullable,
    }
    if options is not None:
        field_input["options"] = options
    if default_value is not None:
        field_input["defaultValue"] = default_value
    if settings is not None:
        field_input["settings"] = settings

    result = gql(
        """
        mutation CreateField($input: CreateOneFieldMetadataInput!) {
          createOneField(input: $input) { id name }
        }
        """,
        {"input": {"field": field_input}},
    )
    field = result.get("createOneField")
    if field:
        print(f"    ✓ Campo '{name}' ({field_type})")
        return True
    print(f"    ✗ Campo '{name}' falló")
    return False


def create_relation(
    from_object_id: str,
    from_field_name: str,
    from_field_label: str,
    to_object_id: str,
    to_field_name: str,
    to_field_label: str,
    relation_type: str = "MANY_TO_ONE",
) -> bool:
    """Crea una relación entre dos objetos.

    relationCreationPayload es tipo JSON en la API — el tipo de relación debe
    pasarse como string dentro del JSON, no como enum GraphQL inline.
    """
    result = gql(
        """
        mutation CreateRelation($input: CreateOneFieldMetadataInput!) {
          createOneField(input: $input) { id name }
        }
        """,
        {
            "input": {
                "field": {
                    "objectMetadataId": from_object_id,
                    "type": "RELATION",
                    "name": from_field_name,
                    "label": from_field_label,
                    "isNullable": True,
                    # JSON scalar: usar las claves que espera la API de Twenty
                    "relationCreationPayload": {
                        "type": relation_type,
                        "targetObjectMetadataId": to_object_id,
                        "targetFieldName": to_field_name,
                        "targetFieldLabel": to_field_label,
                        "targetFieldIcon": "IconFileText",
                    },
                }
            }
        },
    )
    field = result.get("createOneField")
    if field:
        print(f"    ✓ Relación '{from_field_name}' → objeto {to_object_id}")
        return True
    print(f"    ✗ Relación '{from_field_name}' falló")
    return False


# ── Paletas de color para SELECT/MULTI_SELECT ─────────────────────────────────

COLORS = ["green", "blue", "orange", "red", "purple", "yellow", "pink",
          "sky", "turquoise", "darkOrange", "gray"]


def _to_snake(label: str) -> str:
    """Convierte label a UPPER_SNAKE_CASE válido: sin tildes, sin chars especiales, sin dobles __."""
    import re
    val = label.upper()
    # Normalizar tildes y ñ
    for a, b in [("Á","A"),("É","E"),("Í","I"),("Ó","O"),("Ú","U"),("Ñ","N"),
                  ("Ä","A"),("Ë","E"),("Ï","I"),("Ö","O"),("Ü","U")]:
        val = val.replace(a, b)
    # Reemplazar cualquier caracter no alfanumérico por _
    val = re.sub(r"[^A-Z0-9]+", "_", val)
    # Eliminar underscores al inicio/fin
    val = val.strip("_")
    return val


def make_options(labels: list[str], colors: list[str] = None) -> list[dict]:
    if colors is None:
        colors = COLORS
    return [
        {
            "id": str(uuid.uuid4()),  # Twenty requiere UUID válido
            "value": _to_snake(label),
            "label": label,
            "color": colors[i % len(colors)],
            "position": i,
        }
        for i, label in enumerate(labels)
    ]


# ── Definición de objetos y campos ────────────────────────────────────────────

def setup_agente(object_id: str, ws_member_id: str = None):
    print("\n  Campos de Agente:")
    existing = get_existing_fields(object_id)

    # ── Identidad y contacto ──────────────────────────────────────────────────
    create_field(object_id, "TEXT",   "claveAgente",  "CUA",
                 "Clave Única de Agente asignada por GNP", "IconId",
                 existing=existing)
    create_field(object_id, "TEXT",   "rfc",          "RFC",
                 "Registro Federal de Contribuyentes del agente", "IconId",
                 existing=existing)
    create_field(object_id, "PHONES", "celular",      "Celular / WhatsApp",
                 "WhatsApp principal para notificaciones automáticas", "IconPhone",
                 existing=existing)
    create_field(object_id, "EMAILS", "email",        "Email",
                 "Correo de contacto del agente (usado por el pipeline de ingesta)", "IconMail",
                 existing=existing)

    # ── Regulatorio CNSF ──────────────────────────────────────────────────────
    create_field(object_id, "TEXT", "cedula", "Cédula CNSF",
                 "Número de cédula de agente emitida por CNSF", "IconLicense",
                 existing=existing)
    create_field(object_id, "DATE", "fechaVencimientoCedula", "Vencimiento Cédula CNSF",
                 "Fecha de vencimiento de la cédula ante CNSF — genera alerta 30 días antes",
                 "IconCalendarOff", existing=existing)

    # ── Clasificación en la promotoría ────────────────────────────────────────
    create_field(
        object_id, "SELECT", "nivel", "Nivel",
        "Nivel de desarrollo del agente en la promotoría", "IconTrendingUp",
        options=make_options(["Arranque", "Consolidado"], ["orange", "green"]),
        existing=existing,
    )
    create_field(
        object_id, "SELECT", "tipoPersona", "Tipo de Persona",
        "Persona Física o Moral — afecta el manejo fiscal de comisiones", "IconUserSquare",
        options=make_options(["Persona Física", "Persona Moral"], ["blue", "purple"]),
        existing=existing,
    )
    create_field(
        object_id, "MULTI_SELECT", "ramos", "Ramos Autorizados",
        "Ramos de seguros en los que el agente está habilitado para operar", "IconShield",
        options=make_options(["Vida", "GMM", "PyMES", "Autos", "Daños"],
                             ["green", "blue", "orange", "purple", "red"]),
        existing=existing,
    )
    create_field(object_id, "DATE",    "fechaAlta",         "Fecha de Alta",
                 "Fecha de alta del agente en la promotoría", "IconCalendarPlus",
                 existing=existing)
    create_field(object_id, "BOOLEAN", "activo",            "Activo",
                 "Si el agente está activo — los inactivos no reciben nuevos trámites",
                 "IconCheck", default_value=True, existing=existing)
    create_field(object_id, "TEXT",    "promotoriaAsignada","Promotoría Asignada",
                 "Nombre descriptivo de la promotoría o gerencia responsable (legacy)",
                 "IconBuilding", existing=existing)

    # ── Estatus del agente (reemplaza la semántica de activo BOOLEAN) ─────────
    create_field(
        object_id, "SELECT", "estatus", "Estatus",
        "Estado del agente en la promotoría — Prospecto para nuevos antes de activar",
        "IconCircleDot",
        options=make_options(["Activo", "Inactivo", "Prospecto"],
                             ["green", "gray", "orange"]),
        existing=existing,
    )
    # Nivel actualizado con la opción Top (agentes de alto volumen)
    if "nivel" not in existing:
        create_field(
            object_id, "SELECT", "nivel", "Nivel",
            "Nivel de desarrollo del agente en la promotoría", "IconTrendingUp",
            options=make_options(["Arranque", "Consolidado", "Top"],
                                 ["orange", "green", "purple"]),
            existing=existing,
        )

    # ── Relación al Gerente de Desarrollo asignado ────────────────────────────
    if ws_member_id and "gerenteDesarrollo" not in existing:
        print("    Relación agente → gerenteDesarrollo (workspaceMember):")
        create_relation(
            from_object_id=object_id,
            from_field_name="gerenteDesarrollo",
            from_field_label="Gerente de Desarrollo",
            to_object_id=ws_member_id,
            to_field_name="agentesAsignados",
            to_field_label="Agentes Asignados",
            relation_type="MANY_TO_ONE",
        )
    elif "gerenteDesarrollo" in existing:
        print("    — Relación 'gerenteDesarrollo' ya existe, omitiendo")


def setup_tramite(object_id: str, agente_id: str, ws_member_id: str = None):
    print("\n  Campos de Trámite:")
    existing = get_existing_fields(object_id)

    # ── Identificación ────────────────────────────────────────────────────────
    create_field(object_id, "TEXT", "folio",        "Folio Interno",
                 "Folio secuencial interno de la promotoría (TRM-YYYY-NNNNN)", "IconHash",
                 existing=existing)
    create_field(object_id, "TEXT", "folioGnp",     "Folio GNP",
                 "Folio asignado por GNP al turnar el trámite", "IconHash",
                 existing=existing)
    create_field(object_id, "TEXT", "numeroPoliza", "Número de Póliza",
                 "Número de póliza GNP emitida o afectada por el trámite", "IconFileCheck",
                 existing=existing)

    # ── Clasificación ─────────────────────────────────────────────────────────
    create_field(
        object_id, "SELECT", "ramo", "Ramo",
        "Ramo de seguros del trámite", "IconShield",
        options=make_options(["Vida", "GMM", "PyMES", "Autos", "Daños"],
                             ["green", "blue", "orange", "purple", "red"]),
        existing=existing,
    )
    create_field(
        object_id, "SELECT", "tipoTramite", "Tipo de Trámite",
        "Tipo de operación del trámite", "IconFileText",
        options=make_options(
            ["Emisión", "Endoso", "Siniestro", "Renovación", "Cancelación"],
            ["blue", "orange", "red", "green", "gray"],
        ),
        existing=existing,
    )
    create_field(
        object_id, "SELECT", "estatus", "Estatus",
        "Estado actual en el flujo de trabajo de la promotoría", "IconProgress",
        options=make_options(
            ["Recibido", "En Revisión Doc", "Documentación Completa",
             "Turnado GNP", "En Proceso GNP", "Detenido", "Resuelto", "Cancelado"],
            ["sky", "orange", "blue", "purple", "turquoise", "red", "green", "gray"],
        ),
        existing=existing,
    )
    create_field(
        object_id, "SELECT", "prioridad", "Prioridad",
        "Nivel de urgencia asignado por el analista o gerente", "IconFlag",
        options=make_options(["Normal", "Alta", "Urgente"],
                             ["green", "orange", "red"]),
        existing=existing,
    )
    create_field(
        object_id, "SELECT", "canalIngreso", "Canal de Ingreso",
        "Medio por el que llegó el trámite a la promotoría", "IconInbox",
        options=make_options(["WhatsApp", "Correo", "Manual"],
                             ["green", "blue", "gray"]),
        existing=existing,
    )

    # ── Fechas del ciclo de vida ───────────────────────────────────────────────
    create_field(object_id, "DATE_TIME", "fechaIngreso",             "Fecha de Ingreso",
                 "Cuándo llegó el trámite a la promotoría", "IconCalendar",
                 existing=existing)
    create_field(object_id, "DATE",      "fechaLimiteDocumentacion", "Límite Documentación",
                 "Fecha máxima para completar documentos antes de perder vigencia",
                 "IconCalendarDue", existing=existing)
    create_field(object_id, "DATE_TIME", "fechaTurnoGnp",            "Fecha Turno GNP",
                 "Cuándo se subió el trámite a la plataforma de GNP", "IconCalendarUp",
                 existing=existing)
    create_field(object_id, "DATE_TIME", "fechaResolucion",          "Fecha Resolución",
                 "Cuándo GNP emitió resolución (positiva o negativa)", "IconCalendarCheck",
                 existing=existing)

    # ── Contenido y montos ────────────────────────────────────────────────────
    create_field(object_id, "CURRENCY",  "monto",           "Prima / Monto",
                 "Prima anual, costo del endoso o monto del siniestro según tipo de trámite",
                 "IconCurrencyDollar", existing=existing)
    create_field(object_id, "RICH_TEXT", "motivoDetencion", "Motivo de Detención",
                 "Razón por la que GNP detuvo el trámite — completar al contactar a GNP",
                 "IconAlertTriangle", existing=existing)
    create_field(object_id, "RICH_TEXT", "notasInternas",   "Notas Internas",
                 "Notas del analista visibles solo para el equipo interno", "IconNote",
                 existing=existing)

    # ── SLA tracking ─────────────────────────────────────────────────────────
    create_field(object_id, "DATE_TIME", "fechaLimiteSla", "Fecha Límite SLA",
                 "Deadline de SLA calculado por add_business_days() en Supabase según reglas_negocio",
                 "IconClockExclamation", existing=existing)
    create_field(
        object_id, "SELECT", "slaEstatus", "Estatus SLA",
        "Semáforo de cumplimiento del SLA — actualizado por CRON diario", "IconGauge",
        options=make_options(["A Tiempo", "En Riesgo", "Vencido"],
                             ["green", "orange", "red"]),
        existing=existing,
    )
    # ── Ubicación del balón (responsabilidad actual) ──────────────────────────
    create_field(
        object_id, "SELECT", "ubicacionBalon", "Balón en",
        "¿Quién tiene la pelota? Indica dónde está la responsabilidad de avanzar el trámite",
        "IconBall",
        options=make_options(["Promotoría", "Agente", "GNP"],
                             ["blue", "orange", "purple"]),
        existing=existing,
    )

    # ── Relaciones principales ────────────────────────────────────────────────
    if "agente" not in existing:
        print("    Relación tramite → agente:")
        create_relation(
            from_object_id=object_id,
            from_field_name="agente",
            from_field_label="Agente",
            to_object_id=agente_id,
            to_field_name="tramites",
            to_field_label="Trámites",
            relation_type="MANY_TO_ONE",
        )
    else:
        print("    — Relación 'agente' ya existe, omitiendo")

    # Relaciones con equipo interno
    if ws_member_id:
        if "analistaAsignado" not in existing:
            print("    Relación tramite → analistaAsignado (workspaceMember):")
            create_relation(
                from_object_id=object_id,
                from_field_name="analistaAsignado",
                from_field_label="Analista Asignado",
                to_object_id=ws_member_id,
                to_field_name="tramitesComoAnalista",
                to_field_label="Trámites (Analista)",
                relation_type="MANY_TO_ONE",
            )
        else:
            print("    — Relación 'analistaAsignado' ya existe, omitiendo")

        if "gerenteRamo" not in existing:
            print("    Relación tramite → gerenteRamo (workspaceMember):")
            create_relation(
                from_object_id=object_id,
                from_field_name="gerenteRamo",
                from_field_label="Gerente de Ramo",
                to_object_id=ws_member_id,
                to_field_name="tramitesComoGerente",
                to_field_label="Trámites (Gerente)",
                relation_type="MANY_TO_ONE",
            )
        else:
            print("    — Relación 'gerenteRamo' ya existe, omitiendo")


def setup_documento_tramite(object_id: str, tramite_id: str):
    print("\n  Campos de DocumentoTramite:")
    existing = get_existing_fields(object_id)

    # Campos básicos (FILES requiere settings.maxNumberOfValues)
    create_field(object_id, "DATE_TIME", "fechaRecepcion", "Fecha de Recepción",
                 "Cuándo se recibió el documento", "IconCalendar", existing=existing)
    create_field(object_id, "TEXT", "motivoRechazo", "Motivo de Rechazo",
                 "Razón por la que fue rechazado", "IconX", existing=existing)
    create_field(object_id, "FILES", "archivo", "Archivo",
                 "Documento adjunto", "IconFile",
                 settings={"maxNumberOfValues": 5}, existing=existing)

    # ── Metadatos de integridad y procesamiento IA ────────────────────────────
    create_field(object_id, "TEXT",    "urlStorage",    "URL en Storage",
                 "URL de Supabase Storage donde reside el archivo procesado", "IconLink",
                 existing=existing)
    create_field(object_id, "BOOLEAN", "esProtegido",   "Protegido con contraseña",
                 "El documento tiene contraseña — requiere intervención manual para desencriptar",
                 "IconLock", default_value=False, existing=existing)
    create_field(object_id, "BOOLEAN", "ocrValidado",   "OCR Validado",
                 "El texto fue extraído y validado por OCR o por lectura directa del PDF",
                 "IconScan", default_value=False, existing=existing)
    create_field(object_id, "TEXT",    "hashIntegridad","Hash de Integridad",
                 "SHA-256 del archivo — detecta duplicados y verifica integridad post-descarga",
                 "IconFingerprint", existing=existing)

    # SELECT: tipo de documento
    create_field(
        object_id, "SELECT", "tipoDocumento", "Tipo de Documento",
        "Tipo de documento según checklist del ramo", "IconFileDescription",
        options=make_options([
            "INE / Pasaporte", "Acta de Nacimiento", "Solicitud Firmada",
            "Comprobante de Domicilio", "Cuestionario Médico",
            "Designación de Beneficiarios", "Comprobante de Pago",
            "RFC", "Acta Constitutiva", "Poder Notarial",
            "Tarjeta Circulación / Factura", "Licencia de Conducir",
            "Fotografías del Vehículo", "Inventario de Bienes",
            "Estados Financieros", "Formato GNP", "Otro",
        ]),
        existing=existing,
    )

    # SELECT: estatus del documento
    create_field(
        object_id, "SELECT", "estatusDocumento", "Estatus del Documento",
        "Estado de revisión del documento", "IconCircleCheck",
        options=make_options(
            ["Pendiente", "Recibido", "Aceptado", "Rechazado"],
            ["gray", "blue", "green", "red"],
        ),
        existing=existing,
    )

    # Relación DocumentoTramite → Tramite
    if "tramite" not in existing:
        print("    Relación documentoTramite → tramite:")
        create_relation(
            from_object_id=object_id,
            from_field_name="tramite",
            from_field_label="Trámite",
            to_object_id=tramite_id,
            to_field_name="documentos",
            to_field_label="Documentos",
            relation_type="MANY_TO_ONE",
        )
    else:
        print("    — Relación 'tramite' ya existe, omitiendo")


def setup_alerta_tramite(object_id: str, tramite_id: str):
    print("\n  Campos de AlertaTramite:")
    existing = get_existing_fields(object_id)

    create_field(object_id, "DATE_TIME", "fechaEnvio", "Fecha de Envío",
                 "Cuándo se envió la alerta", "IconCalendar", existing=existing)
    create_field(object_id, "BOOLEAN", "respondido", "Respondido",
                 "Si el agente respondió la alerta", "IconCheck",
                 default_value=False, existing=existing)
    create_field(object_id, "RICH_TEXT", "mensaje", "Mensaje",
                 "Contenido del mensaje enviado", "IconMessage", existing=existing)

    # SELECT: tipo de alerta
    create_field(
        object_id, "SELECT", "tipoAlerta", "Tipo de Alerta",
        "Motivo de la notificación enviada", "IconBell",
        options=make_options(
            ["Documentación Incompleta", "Trámite Detenido",
             "Resolución Disponible", "Recordatorio"],
            ["orange", "red", "green", "blue"],
        ),
        existing=existing,
    )

    # SELECT: canal de notificación
    create_field(
        object_id, "SELECT", "canal", "Canal",
        "Canal por el que se envió la alerta", "IconBrandWhatsapp",
        options=make_options(["WhatsApp", "Email", "Interno"],
                             ["green", "blue", "gray"]),
        existing=existing,
    )

    # Relación AlertaTramite → Tramite
    if "tramite" not in existing:
        print("    Relación alertaTramite → tramite:")
        create_relation(
            from_object_id=object_id,
            from_field_name="tramite",
            from_field_label="Trámite",
            to_object_id=tramite_id,
            to_field_name="alertas",
            to_field_label="Alertas",
            relation_type="MANY_TO_ONE",
        )
    else:
        print("    — Relación 'tramite' ya existe, omitiendo")


def setup_asegurado(object_id: str):
    print("\n  Campos de Asegurado:")
    existing = get_existing_fields(object_id)

    # ── Identificación (documentos MX obligatorios para seguros) ─────────────
    create_field(object_id, "TEXT", "rfc",  "RFC",
                 "RFC del asegurado — obligatorio para emisión de póliza", "IconId",
                 existing=existing)
    create_field(object_id, "TEXT", "curp", "CURP",
                 "Clave Única de Registro de Población — requerida por CNSF para Vida y GMM",
                 "IconId", existing=existing)

    # ── Contacto ──────────────────────────────────────────────────────────────
    create_field(object_id, "PHONES", "celular", "Celular / WhatsApp",
                 "Teléfono celular principal del asegurado", "IconPhone", existing=existing)
    create_field(object_id, "EMAILS", "email",   "Email",
                 "Correo electrónico del asegurado", "IconMail", existing=existing)

    # ── Datos personales relevantes para suscripción ──────────────────────────
    create_field(object_id, "DATE", "fechaNacimiento", "Fecha de Nacimiento",
                 "Usada para calcular edad de aceptación y alertas de renovación por edad máxima",
                 "IconCalendar", existing=existing)
    create_field(
        object_id, "SELECT", "genero", "Género",
        "Género del asegurado — incide en la prima actuarial de Vida y GMM", "IconUser",
        options=make_options(["Masculino", "Femenino"], ["blue", "pink"]),
        existing=existing,
    )
    create_field(
        object_id, "SELECT", "estadoCivil", "Estado Civil",
        "Estado civil — relevante para designación de beneficiarios en siniestros de fallecimiento",
        "IconHeart",
        options=make_options(
            ["Soltero/a", "Casado/a", "Divorciado/a", "Viudo/a", "Unión Libre"],
            ["blue", "green", "orange", "gray", "purple"],
        ),
        existing=existing,
    )
    create_field(object_id, "TEXT", "ocupacion", "Ocupación",
                 "Ocupación del asegurado — GNP la requiere para suscripción de GMM/Vida de alto riesgo",
                 "IconBriefcase", existing=existing)
    create_field(object_id, "RICH_TEXT", "notas", "Notas",
                 "Observaciones internas sobre el asegurado", "IconNote",
                 existing=existing)


def setup_colaborador(object_id: str, agente_id: str):
    print("\n  Campos de Colaborador:")
    existing = get_existing_fields(object_id)

    # ── Identidad ─────────────────────────────────────────────────────────────
    create_field(object_id, "TEXT", "rfc",              "RFC",
                 "RFC del colaborador — necesario para pago de comisiones compartidas",
                 "IconId", existing=existing)
    create_field(object_id, "TEXT", "curp",             "CURP",
                 "CURP del colaborador — requerida por CNSF para registro como sub-agente",
                 "IconId", existing=existing)
    create_field(object_id, "TEXT", "claveColaborador", "Clave Colaborador",
                 "Sub-clave GNP propia del colaborador, si cuenta con una asignada",
                 "IconHash", existing=existing)

    # ── Contacto ──────────────────────────────────────────────────────────────
    create_field(object_id, "PHONES", "celular", "Celular / WhatsApp",
                 "WhatsApp de contacto del colaborador", "IconPhone", existing=existing)
    create_field(object_id, "EMAILS", "email",   "Email",
                 "Correo electrónico del colaborador", "IconMail", existing=existing)

    # ── Rol y capacidades ─────────────────────────────────────────────────────
    create_field(
        object_id, "SELECT", "rolColaborador", "Rol",
        "Función que desempeña el colaborador dentro de la operativa del agente principal",
        "IconBriefcase",
        options=make_options(
            ["Asistente Administrativo", "Sub-Agente", "Promotor Auxiliar", "Representante de Ventas"],
            ["blue", "green", "orange", "purple"],
        ),
        existing=existing,
    )
    create_field(
        object_id, "MULTI_SELECT", "ramos", "Ramos que Atiende",
        "Ramos de seguros que cubre este colaborador bajo el CUA del agente principal",
        "IconShield",
        options=make_options(["Vida", "GMM", "PyMES", "Autos", "Daños"],
                             ["green", "blue", "orange", "purple", "red"]),
        existing=existing,
    )
    create_field(object_id, "BOOLEAN", "activo", "Activo",
                 "Si el colaborador está activo — los inactivos no aparecen en asignación automática",
                 "IconCheck", default_value=True, existing=existing)
    create_field(object_id, "NUMBER",  "porcentajeParticipacion", "% Participación",
                 "Porcentaje de la comisión del agente principal que corresponde a este colaborador",
                 "IconPercentage", existing=existing)

    # ── Relación principal ────────────────────────────────────────────────────
    if "agentePrincipal" not in existing:
        print("    Relación colaborador → agente principal:")
        create_relation(
            from_object_id=object_id,
            from_field_name="agentePrincipal",
            from_field_label="Agente Principal",
            to_object_id=agente_id,
            to_field_name="colaboradores",
            to_field_label="Colaboradores",
            relation_type="MANY_TO_ONE",
        )
    else:
        print("    — Relación 'agentePrincipal' ya existe, omitiendo")


def setup_tramite_asegurado(tramite_id: str, asegurado_id: str):
    print("\n  Relación adicional Trámite → Asegurado:")
    existing = get_existing_fields(tramite_id)
    if "asegurado" not in existing:
        create_relation(
            from_object_id=tramite_id,
            from_field_name="asegurado",
            from_field_label="Asegurado",
            to_object_id=asegurado_id,
            to_field_name="tramites",
            to_field_label="Trámites",
            relation_type="MANY_TO_ONE",
        )
    else:
        print("    — Relación 'asegurado' ya existe, omitiendo")


def setup_workspace_member_extra(object_id: str):
    print("\n  Campos de WorkspaceMember (equipo interno):")
    existing = get_existing_fields(object_id)

    # ── Rol y especialidad ────────────────────────────────────────────────────
    create_field(
        object_id, "SELECT", "rolInterno", "Rol Interno",
        "Función dentro de la estructura operativa de la promotoría", "IconBriefcase",
        options=make_options(
            ["Analista", "Gerente de Ramo", "Gerente de Desarrollo", "Director de Operaciones"],
            ["blue", "purple", "orange", "red"],
        ),
        existing=existing,
    )
    create_field(
        object_id, "SELECT", "ramo", "Ramo de Especialidad",
        "Ramo de seguros que atiende — define qué trámites se le asignan automáticamente",
        "IconShield",
        options=make_options(
            ["Vida", "GMM", "PyMES", "Autos", "Daños", "Todos"],
            ["green", "blue", "orange", "purple", "red", "gray"],
        ),
        existing=existing,
    )

    # ── Productividad ─────────────────────────────────────────────────────────
    create_field(object_id, "NUMBER", "metaProductividad", "Meta Mensual de Trámites",
                 "Número de trámites que debe procesar por mes — base para reportes de desempeño",
                 "IconTarget", existing=existing)
    create_field(object_id, "DATE",   "fechaInicioFunciones", "Fecha de Inicio",
                 "Fecha en que comenzó en su rol actual dentro de la promotoría",
                 "IconCalendarPlus", existing=existing)


# ── Nuevos objetos: Capa II y III ─────────────────────────────────────────────

def setup_producto(object_id: str):
    print("\n  Campos de Producto:")
    existing = get_existing_fields(object_id)

    create_field(object_id, "TEXT",    "clave",            "Clave",
                 "Clave interna del producto (Ej: VIDA_IND_TOTAL)", "IconHash",
                 existing=existing)
    create_field(object_id, "TEXT",    "nombreComercial",  "Nombre Comercial",
                 "Nombre del producto tal como lo conoce GNP y los agentes", "IconTag",
                 existing=existing)
    create_field(
        object_id, "SELECT", "ramo", "Ramo",
        "Ramo de seguros al que pertenece el producto", "IconShield",
        options=make_options(["Vida", "GMM", "PyMES", "Autos", "Daños"],
                             ["green", "blue", "orange", "purple", "red"]),
        existing=existing,
    )
    create_field(object_id, "TEXT",    "aseguradora",      "Aseguradora",
                 "Aseguradora que respalda el producto (default: GNP)", "IconBuilding",
                 existing=existing)
    create_field(object_id, "NUMBER",  "vigenciaMeses",    "Vigencia (meses)",
                 "Duración estándar de la póliza en meses (12 para anuales)", "IconCalendar",
                 existing=existing)
    create_field(object_id, "CURRENCY","primaReferencia",  "Prima de Referencia",
                 "Prima anual de referencia orientativa — varía según suscripción", "IconCurrencyDollar",
                 existing=existing)
    create_field(object_id, "TEXT",    "descripcion",      "Descripción",
                 "Descripción breve del producto y sus coberturas principales", "IconFileText",
                 existing=existing)
    create_field(object_id, "BOOLEAN", "activo",           "Activo",
                 "Si el producto está vigente y puede usarse en nuevos trámites",
                 "IconCheck", default_value=True, existing=existing)


def setup_historial_estatus(object_id: str, tramite_id: str):
    print("\n  Campos de HistorialEstatus:")
    existing = get_existing_fields(object_id)

    create_field(object_id, "TEXT",      "estatusAnterior", "Estatus Anterior",
                 "Estado previo antes del cambio", "IconArrowLeft", existing=existing)
    create_field(object_id, "TEXT",      "estatusNuevo",    "Estatus Nuevo",
                 "Estado al que se cambió", "IconArrowRight", existing=existing)
    create_field(object_id, "DATE_TIME", "fechaCambio",     "Fecha del Cambio",
                 "Cuándo ocurrió la transición de estatus", "IconCalendarEvent",
                 existing=existing)
    create_field(
        object_id, "SELECT", "actor", "Actor",
        "Quién o qué originó el cambio de estatus", "IconUser",
        options=make_options(["Sistema", "Analista", "Gerente", "AI Agent", "Webhook GNP"],
                             ["gray", "blue", "purple", "green", "orange"]),
        existing=existing,
    )
    create_field(object_id, "TEXT",      "motivoRechazo",   "Motivo de Rechazo",
                 "Clave del catálogo motivoRechazo — aplica cuando estatus = Rechazado",
                 "IconX", existing=existing)
    create_field(object_id, "NUMBER",    "duracionHoras",   "Duración en Estatus (hrs)",
                 "Horas que el trámite estuvo en el estatus anterior antes de cambiar",
                 "IconClock", existing=existing)
    create_field(object_id, "TEXT",      "notas",           "Notas",
                 "Contexto adicional del cambio — llenado por el analista o por el agente IA",
                 "IconNote", existing=existing)
    create_field(
        object_id, "SELECT", "fuente", "Fuente",
        "Origen del cambio de estatus", "IconPlug",
        options=make_options(["Pipeline", "CRM Manual", "Webhook GNP", "CRON"],
                             ["blue", "green", "orange", "gray"]),
        existing=existing,
    )

    if "tramite" not in existing:
        print("    Relación historialEstatus → tramite:")
        create_relation(
            from_object_id=object_id,
            from_field_name="tramite",
            from_field_label="Trámite",
            to_object_id=tramite_id,
            to_field_name="historialEstatus",
            to_field_label="Historial de Estatus",
            relation_type="MANY_TO_ONE",
        )
    else:
        print("    — Relación 'tramite' ya existe, omitiendo")


def setup_nota_interaccion(object_id: str, tramite_id: str, agente_id: str):
    print("\n  Campos de NotaInteraccion:")
    existing = get_existing_fields(object_id)

    create_field(
        object_id, "SELECT", "tipo", "Tipo",
        "Canal o tipo de interacción registrada", "IconMessageCircle",
        options=make_options(["Email", "WhatsApp", "Nota Interna", "Llamada"],
                             ["blue", "green", "gray", "orange"]),
        existing=existing,
    )
    create_field(object_id, "TEXT",      "asunto",       "Asunto",
                 "Asunto del correo o título de la nota", "IconTextCaption",
                 existing=existing)
    create_field(object_id, "RICH_TEXT", "contenido",    "Contenido",
                 "Cuerpo completo de la comunicación", "IconFileText",
                 existing=existing)
    create_field(object_id, "TEXT",      "resumenIa",    "Resumen IA",
                 "Resumen de 2-3 oraciones generado por Claude a partir del contenido",
                 "IconSparkles", existing=existing)
    create_field(
        object_id, "SELECT", "sentimiento", "Sentimiento",
        "Análisis de tono detectado por la IA — indica satisfacción del agente", "IconMoodSmile",
        options=make_options(["Positivo", "Neutro", "Negativo"],
                             ["green", "gray", "red"]),
        existing=existing,
    )
    create_field(object_id, "TEXT",      "hiloId",       "ID de Hilo",
                 "Gmail Thread-ID o ID de conversación WhatsApp para agrupar mensajes relacionados",
                 "IconGitBranch", existing=existing)
    create_field(object_id, "TEXT",      "autorEmail",   "Email del Autor",
                 "Dirección de correo de quien generó la interacción", "IconAt",
                 existing=existing)
    create_field(object_id, "BOOLEAN",   "urgenciaDetectada", "Urgencia Detectada",
                 "La IA detectó lenguaje urgente o señales de insatisfacción alta",
                 "IconAlertTriangle", default_value=False, existing=existing)
    create_field(object_id, "DATE_TIME", "fechaInteraccion", "Fecha de Interacción",
                 "Cuándo ocurrió la interacción (no cuándo se registró)", "IconCalendar",
                 existing=existing)

    # Relación → Tramite (muchas notas a un tramite)
    if "tramite" not in existing:
        print("    Relación notaInteraccion → tramite:")
        create_relation(
            from_object_id=object_id,
            from_field_name="tramite",
            from_field_label="Trámite",
            to_object_id=tramite_id,
            to_field_name="notas",
            to_field_label="Notas e Interacciones",
            relation_type="MANY_TO_ONE",
        )
    else:
        print("    — Relación 'tramite' ya existe, omitiendo")

    # Relación → Agente (notas de seguimiento directo al agente)
    if "agente" not in existing:
        print("    Relación notaInteraccion → agente:")
        create_relation(
            from_object_id=object_id,
            from_field_name="agente",
            from_field_label="Agente",
            to_object_id=agente_id,
            to_field_name="interacciones",
            to_field_label="Interacciones",
            relation_type="MANY_TO_ONE",
        )
    else:
        print("    — Relación 'agente' ya existe, omitiendo")


def setup_gnp_portal_mirror(object_id: str, tramite_id: str):
    print("\n  Campos de GnpPortalMirror:")
    existing = get_existing_fields(object_id)

    create_field(object_id, "TEXT",      "estatusOficialGnp",     "Estatus Oficial GNP",
                 "Estatus exacto como aparece en el portal interno de GNP", "IconExternalLink",
                 existing=existing)
    create_field(object_id, "TEXT",      "comentariosSuscriptor", "Comentarios del Suscriptor",
                 "Comentarios del suscriptor de GNP al revisar el trámite", "IconMessage",
                 existing=existing)
    create_field(object_id, "CURRENCY",  "primaCalculadaGnp",     "Prima Calculada GNP",
                 "Prima calculada por GNP en su sistema — puede diferir de la estimada",
                 "IconCurrencyDollar", existing=existing)
    create_field(object_id, "TEXT",      "motivoRechazoGnp",      "Motivo Rechazo GNP",
                 "Razón específica de GNP si el trámite fue rechazado en su plataforma",
                 "IconX", existing=existing)
    create_field(object_id, "TEXT",      "suscriptorGnp",         "Suscriptor GNP",
                 "Nombre del suscriptor de GNP asignado al trámite", "IconUserCircle",
                 existing=existing)
    create_field(object_id, "DATE_TIME", "fechaSincronizacion",   "Última Sincronización",
                 "Cuándo se actualizó este registro por última vez desde el portal GNP",
                 "IconRefresh", existing=existing)
    create_field(object_id, "TEXT",      "urlPortalGnp",          "URL en Portal GNP",
                 "Enlace directo al expediente en el portal interno de GNP (si disponible)",
                 "IconLink", existing=existing)
    create_field(object_id, "BOOLEAN",   "requiereAccion",        "Requiere Acción",
                 "GNP solicitó información adicional o acción de la promotoría",
                 "IconFlag", default_value=False, existing=existing)

    if "tramite" not in existing:
        print("    Relación gnpPortalMirror → tramite (1:1):")
        create_relation(
            from_object_id=object_id,
            from_field_name="tramite",
            from_field_label="Trámite",
            to_object_id=tramite_id,
            to_field_name="gnpMirror",
            to_field_label="Estado en Portal GNP",
            relation_type="MANY_TO_ONE",  # Twenty no tiene 1:1 nativo; se controla por lógica
        )
    else:
        print("    — Relación 'tramite' ya existe, omitiendo")


def setup_hilo_conversacion(object_id: str, tramite_id: str, agente_id: str):
    print("\n  Campos de HiloConversacion:")
    existing = get_existing_fields(object_id)

    create_field(object_id, "TEXT",      "gmailThreadId",   "Gmail Thread ID",
                 "ID del hilo de Gmail — clave para deduplicación de correos relacionados",
                 "IconBrandGmail", existing=existing)
    create_field(object_id, "TEXT",      "asunto",          "Asunto",
                 "Asunto del primer correo del hilo", "IconTextCaption",
                 existing=existing)
    create_field(
        object_id, "SELECT", "canal", "Canal",
        "Canal de comunicación del hilo", "IconMessage",
        options=make_options(["Correo", "WhatsApp"], ["blue", "green"]),
        existing=existing,
    )
    create_field(object_id, "NUMBER",    "totalMensajes",   "Total Mensajes",
                 "Número de mensajes en el hilo hasta la última sincronización", "IconHash",
                 existing=existing)
    create_field(object_id, "DATE_TIME", "ultimaActividad", "Última Actividad",
                 "Cuándo llegó el último mensaje al hilo", "IconClock",
                 existing=existing)
    create_field(object_id, "BOOLEAN",   "requiereAtencion","Requiere Atención",
                 "El hilo tiene mensajes no respondidos o urgentes sin tramite vinculado",
                 "IconBellRinging", default_value=False, existing=existing)
    create_field(object_id, "TEXT",      "emailRemitente",  "Email Remitente",
                 "Dirección de correo principal del hilo", "IconAt", existing=existing)

    if "tramite" not in existing:
        print("    Relación hiloConversacion → tramite:")
        create_relation(
            from_object_id=object_id,
            from_field_name="tramite",
            from_field_label="Trámite",
            to_object_id=tramite_id,
            to_field_name="hilos",
            to_field_label="Hilos de Conversación",
            relation_type="MANY_TO_ONE",
        )
    else:
        print("    — Relación 'tramite' ya existe, omitiendo")

    if "agente" not in existing:
        print("    Relación hiloConversacion → agente:")
        create_relation(
            from_object_id=object_id,
            from_field_name="agente",
            from_field_label="Agente",
            to_object_id=agente_id,
            to_field_name="hilosConversacion",
            to_field_label="Hilos de Conversación",
            relation_type="MANY_TO_ONE",
        )
    else:
        print("    — Relación 'agente' ya existe, omitiendo")


def setup_kpi_snapshot(object_id: str):
    print("\n  Campos de KpiSnapshot:")
    existing = get_existing_fields(object_id)

    create_field(object_id, "DATE",      "fechaCorte",   "Fecha de Corte",
                 "Fecha hasta la que se calculó el KPI", "IconCalendarStats",
                 existing=existing)
    create_field(object_id, "TEXT",      "metricaNombre","Métrica",
                 "Nombre de la métrica (Ej: SLA_Compliance_Global, Tasa_Rechazo_Vida)",
                 "IconChartBar", existing=existing)
    create_field(
        object_id, "SELECT", "granularidad", "Granularidad",
        "Período de agregación del KPI", "IconCalendarRepeat",
        options=make_options(["Diario", "Semanal", "Mensual"], ["blue", "green", "purple"]),
        existing=existing,
    )
    create_field(
        object_id, "SELECT", "entidadTipo", "Tipo de Entidad",
        "Nivel al que aplica la métrica", "IconLayers",
        options=make_options(["Global", "Ramo", "Agente", "Analista"],
                             ["gray", "blue", "green", "orange"]),
        existing=existing,
    )
    create_field(object_id, "TEXT",      "entidadId",   "ID de Entidad",
                 "ID del ramo, agente o analista al que aplica — vacío si es Global",
                 "IconHash", existing=existing)
    create_field(object_id, "NUMBER",    "valor",       "Valor",
                 "Valor calculado de la métrica", "IconTrendingUp", existing=existing)
    create_field(object_id, "NUMBER",    "meta",        "Meta",
                 "Valor objetivo o target de la métrica para el período", "IconTarget",
                 existing=existing)
    create_field(object_id, "BOOLEAN",   "metaAlcanzada", "Meta Alcanzada",
                 "Si el valor >= meta para este período", "IconCircleCheck",
                 default_value=False, existing=existing)
    create_field(object_id, "TEXT",      "unidad",      "Unidad",
                 "Unidad de medida (%, horas, tramites, pesos)", "IconRuler",
                 existing=existing)


def setup_agent_performance_monthly(object_id: str, agente_id: str):
    print("\n  Campos de AgentPerformanceMonthly:")
    existing = get_existing_fields(object_id)

    create_field(object_id, "TEXT",     "mesAnio",                   "Mes / Año",
                 "Período en formato MM-YYYY (Ej: 04-2026)", "IconCalendarStats",
                 existing=existing)
    create_field(object_id, "NUMBER",   "tramitesTotales",           "Trámites Totales",
                 "Total de trámites enviados por el agente en el período", "IconStack",
                 existing=existing)
    create_field(object_id, "NUMBER",   "tramitesResueltos",         "Trámites Resueltos",
                 "Trámites con estatus Resuelto en el período", "IconCircleCheck",
                 existing=existing)
    create_field(object_id, "NUMBER",   "tramitesRechazados",        "Trámites Rechazados",
                 "Trámites que llegaron incompletos y fueron rechazados", "IconCircleX",
                 existing=existing)
    create_field(object_id, "NUMBER",   "firstPassYield",            "First Pass Yield (%)",
                 "% de trámites que pasaron revisión documental sin rechazo en el primer intento",
                 "IconBadgeCheck", existing=existing)
    create_field(object_id, "NUMBER",   "promediodocsDocsFaltantes", "Promedio Docs Faltantes",
                 "Promedio de documentos que faltan por trámite — indica calidad documental",
                 "IconPaperclip", existing=existing)
    create_field(object_id, "CURRENCY", "primaEmitida",              "Prima Emitida",
                 "Suma de primas de pólizas emitidas en el período", "IconCurrencyDollar",
                 existing=existing)
    create_field(object_id, "NUMBER",   "tasaCumplimientoSla",       "Cumplimiento SLA (%)",
                 "% de trámites resueltos dentro del SLA acordado", "IconGauge",
                 existing=existing)
    create_field(object_id, "CURRENCY", "bonoProyectado",            "Bono Proyectado",
                 "Bono estimado para el agente según esquema de incentivos de la promotoría",
                 "IconMoneybag", existing=existing)
    create_field(object_id, "BOOLEAN",  "esVigente",                 "Es Vigente",
                 "Si este es el snapshot más reciente para el agente en el período",
                 "IconCheck", default_value=True, existing=existing)

    if "agente" not in existing:
        print("    Relación agentPerformanceMonthly → agente:")
        create_relation(
            from_object_id=object_id,
            from_field_name="agente",
            from_field_label="Agente",
            to_object_id=agente_id,
            to_field_name="performanceMensual",
            to_field_label="Desempeño Mensual",
            relation_type="MANY_TO_ONE",
        )
    else:
        print("    — Relación 'agente' ya existe, omitiendo")


def setup_tramite_producto(tramite_id: str, producto_id: str):
    print("\n  Relación adicional Trámite → Producto:")
    existing = get_existing_fields(tramite_id)
    if "producto" not in existing:
        create_relation(
            from_object_id=tramite_id,
            from_field_name="producto",
            from_field_label="Producto",
            to_object_id=producto_id,
            to_field_name="tramites",
            to_field_label="Trámites",
            relation_type="MANY_TO_ONE",
        )
    else:
        print("    — Relación 'producto' ya existe, omitiendo")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*60}")
    print("  Setup Twenty CRM — Olimpo Promotoría de Seguros")
    print(f"  Endpoint: {METADATA_URL}")
    print(f"{'='*60}\n")

    existing = get_existing_objects()
    print(f"Objetos existentes: {list(existing.keys())}\n")

    object_ids = {}
    # workspaceMember se obtiene primero porque varias funciones lo necesitan
    ws_member_id = existing.get("workspaceMember")
    if ws_member_id:
        print(f"  workspaceMember id: {ws_member_id}")
    else:
        print("  ADVERTENCIA: workspaceMember no encontrado — las relaciones con equipo interno se omitirán")

    # ── 1. Agente ──────────────────────────────────────────────────────────────
    if "agente" in existing:
        print("\n► Agente: ya existe")
        object_ids["agente"] = existing["agente"]
    else:
        print("\n► Creando objeto: Agente")
        oid = create_object(
            name_singular="agente",
            name_plural="agentes",
            label_singular="Agente",
            label_plural="Agentes",
            description="Agente externo de seguros GNP que envía trámites a la promotoría",
            icon="IconUser",
        )
        if not oid:
            print("  ERROR: No se pudo crear Agente. Abortando.")
            sys.exit(1)
        object_ids["agente"] = oid
        time.sleep(0.5)
    setup_agente(object_ids["agente"], ws_member_id)

    # ── 2. Trámite ─────────────────────────────────────────────────────────────
    if "tramite" in existing:
        print("\n► Trámite: ya existe")
        object_ids["tramite"] = existing["tramite"]
    else:
        print("\n► Creando objeto: Trámite")
        oid = create_object(
            name_singular="tramite",
            name_plural="tramites",
            label_singular="Trámite",
            label_plural="Trámites",
            description="Trámite de seguros (póliza, endoso, siniestro, renovación) — objeto central de trabajo",
            icon="IconFileText",
        )
        if not oid:
            print("  ERROR: No se pudo crear Trámite. Abortando.")
            sys.exit(1)
        object_ids["tramite"] = oid
        time.sleep(0.5)
    setup_tramite(object_ids["tramite"], object_ids["agente"], ws_member_id)

    # ── 3. DocumentoTramite ────────────────────────────────────────────────────
    if "documentoTramite" in existing:
        print("\n► DocumentoTramite: ya existe")
        object_ids["documentoTramite"] = existing["documentoTramite"]
    else:
        print("\n► Creando objeto: DocumentoTramite")
        oid = create_object(
            name_singular="documentoTramite",
            name_plural="documentosTramite",
            label_singular="Documento de Trámite",
            label_plural="Documentos de Trámite",
            description="Documento adjunto a un trámite con metadatos de revisión y estatus",
            icon="IconPaperclip",
        )
        if not oid:
            print("  ERROR: No se pudo crear DocumentoTramite.")
        else:
            object_ids["documentoTramite"] = oid
            time.sleep(0.5)
    if "documentoTramite" in object_ids:
        setup_documento_tramite(object_ids["documentoTramite"], object_ids["tramite"])

    # ── 4. AlertaTramite ───────────────────────────────────────────────────────
    if "alertaTramite" in existing:
        print("\n► AlertaTramite: ya existe")
        object_ids["alertaTramite"] = existing["alertaTramite"]
    else:
        print("\n► Creando objeto: AlertaTramite")
        oid = create_object(
            name_singular="alertaTramite",
            name_plural="alertasTramite",
            label_singular="Alerta de Trámite",
            label_plural="Alertas de Trámite",
            description="Registro de notificaciones enviadas al agente sobre sus trámites",
            icon="IconBell",
        )
        if not oid:
            print("  ERROR: No se pudo crear AlertaTramite.")
        else:
            object_ids["alertaTramite"] = oid
            time.sleep(0.5)
    if "alertaTramite" in object_ids:
        setup_alerta_tramite(object_ids["alertaTramite"], object_ids["tramite"])

    # ── 5. Asegurado ───────────────────────────────────────────────────────────
    if "asegurado" in existing:
        print("\n► Asegurado: ya existe")
        object_ids["asegurado"] = existing["asegurado"]
    else:
        print("\n► Creando objeto: Asegurado")
        oid = create_object(
            name_singular="asegurado",
            name_plural="asegurados",
            label_singular="Asegurado",
            label_plural="Asegurados",
            description="Cliente final cubierto por la póliza de seguros",
            icon="IconUserCheck",
        )
        if not oid:
            print("  ERROR: No se pudo crear Asegurado.")
        else:
            object_ids["asegurado"] = oid
            time.sleep(0.5)
    if "asegurado" in object_ids:
        setup_asegurado(object_ids["asegurado"])

    # ── 6. Colaborador ─────────────────────────────────────────────────────────
    if "colaborador" in existing:
        print("\n► Colaborador: ya existe")
        object_ids["colaborador"] = existing["colaborador"]
    else:
        print("\n► Creando objeto: Colaborador")
        oid = create_object(
            name_singular="colaborador",
            name_plural="colaboradores",
            label_singular="Colaborador",
            label_plural="Colaboradores",
            description="Agente secundario que opera bajo el CUA de un agente principal",
            icon="IconUsers",
        )
        if not oid:
            print("  ERROR: No se pudo crear Colaborador.")
        else:
            object_ids["colaborador"] = oid
            time.sleep(0.5)
    if "colaborador" in object_ids:
        setup_colaborador(object_ids["colaborador"], object_ids["agente"])

    # ── 7. Trámite: relación con Asegurado ─────────────────────────────────────
    if "asegurado" in object_ids:
        print("\n► Trámite: añadiendo relación con Asegurado")
        setup_tramite_asegurado(object_ids["tramite"], object_ids["asegurado"])

    # ── 8. WorkspaceMember: campos de equipo interno ───────────────────────────
    if ws_member_id:
        print(f"\n► WorkspaceMember (id={ws_member_id})")
        setup_workspace_member_extra(ws_member_id)
    else:
        print("\n► ADVERTENCIA: workspaceMember no encontrado. Omitiendo campos de equipo interno.")

    # ═══════════════════════════════════════════════════════════════════════════
    # CAPA II y III — Nuevos objetos
    # ═══════════════════════════════════════════════════════════════════════════

    # ── 9. Producto ────────────────────────────────────────────────────────────
    if "producto" in existing:
        print("\n► Producto: ya existe")
        object_ids["producto"] = existing["producto"]
    else:
        print("\n► Creando objeto: Producto")
        oid = create_object(
            name_singular="producto",
            name_plural="productos",
            label_singular="Producto",
            label_plural="Productos",
            description="Producto de seguros GNP que comercializa la promotoría (Vida, GMM, Autos, Daños, PyME)",
            icon="IconShoppingBag",
        )
        if oid:
            object_ids["producto"] = oid
            time.sleep(0.5)
    if "producto" in object_ids:
        setup_producto(object_ids["producto"])

    # ── 9b. Trámite: relación con Producto ────────────────────────────────────
    if "producto" in object_ids:
        print("\n► Trámite: añadiendo relación con Producto")
        setup_tramite_producto(object_ids["tramite"], object_ids["producto"])

    # ── 10. HistorialEstatus ───────────────────────────────────────────────────
    if "historialEstatus" in existing:
        print("\n► HistorialEstatus: ya existe")
        object_ids["historialEstatus"] = existing["historialEstatus"]
    else:
        print("\n► Creando objeto: HistorialEstatus")
        oid = create_object(
            name_singular="historialEstatus",
            name_plural="historialEstatus",
            label_singular="Historial de Estatus",
            label_plural="Historial de Estatus",
            description="Auditoría inmutable de cada cambio de estatus de un trámite — quién lo cambió, cuándo y por qué",
            icon="IconHistory",
        )
        if oid:
            object_ids["historialEstatus"] = oid
            time.sleep(0.5)
    if "historialEstatus" in object_ids:
        setup_historial_estatus(object_ids["historialEstatus"], object_ids["tramite"])

    # ── 11. NotaInteraccion ────────────────────────────────────────────────────
    if "notaInteraccion" in existing:
        print("\n► NotaInteraccion: ya existe")
        object_ids["notaInteraccion"] = existing["notaInteraccion"]
    else:
        print("\n► Creando objeto: NotaInteraccion")
        oid = create_object(
            name_singular="notaInteraccion",
            name_plural="notasInteraccion",
            label_singular="Nota / Interacción",
            label_plural="Notas e Interacciones",
            description="Email, WhatsApp, llamada o nota interna vinculada a un trámite o agente, con resumen IA y análisis de sentimiento",
            icon="IconMessage2",
        )
        if oid:
            object_ids["notaInteraccion"] = oid
            time.sleep(0.5)
    if "notaInteraccion" in object_ids:
        setup_nota_interaccion(
            object_ids["notaInteraccion"],
            object_ids["tramite"],
            object_ids["agente"],
        )

    # ── 12. GnpPortalMirror ───────────────────────────────────────────────────
    if "gnpPortalMirror" in existing:
        print("\n► GnpPortalMirror: ya existe")
        object_ids["gnpPortalMirror"] = existing["gnpPortalMirror"]
    else:
        print("\n► Creando objeto: GnpPortalMirror")
        oid = create_object(
            name_singular="gnpPortalMirror",
            name_plural="gnpPortalMirrors",
            label_singular="Estado en Portal GNP",
            label_plural="Estados en Portal GNP",
            description="Espejo del estado oficial del trámite en el portal interno de GNP — sincronizado manualmente por el analista",
            icon="IconExternalLink",
        )
        if oid:
            object_ids["gnpPortalMirror"] = oid
            time.sleep(0.5)
    if "gnpPortalMirror" in object_ids:
        setup_gnp_portal_mirror(object_ids["gnpPortalMirror"], object_ids["tramite"])

    # ── 13. HiloConversacion ──────────────────────────────────────────────────
    if "hiloConversacion" in existing:
        print("\n► HiloConversacion: ya existe")
        object_ids["hiloConversacion"] = existing["hiloConversacion"]
    else:
        print("\n► Creando objeto: HiloConversacion")
        oid = create_object(
            name_singular="hiloConversacion",
            name_plural="hilosConversacion",
            label_singular="Hilo de Conversación",
            label_plural="Hilos de Conversación",
            description="Hilo de correo o WhatsApp vinculado a un trámite y/o agente — agrupa todos los mensajes de un mismo thread",
            icon="IconGitBranch",
        )
        if oid:
            object_ids["hiloConversacion"] = oid
            time.sleep(0.5)
    if "hiloConversacion" in object_ids:
        setup_hilo_conversacion(
            object_ids["hiloConversacion"],
            object_ids["tramite"],
            object_ids["agente"],
        )

    # ── 14. KpiSnapshot ───────────────────────────────────────────────────────
    if "kpiSnapshot" in existing:
        print("\n► KpiSnapshot: ya existe")
        object_ids["kpiSnapshot"] = existing["kpiSnapshot"]
    else:
        print("\n► Creando objeto: KpiSnapshot")
        oid = create_object(
            name_singular="kpiSnapshot",
            name_plural="kpiSnapshots",
            label_singular="KPI Snapshot",
            label_plural="KPI Snapshots",
            description="Métricas agregadas de operación para directivos — SLA compliance, volumen, tasa de éxito, por período y entidad",
            icon="IconChartLine",
        )
        if oid:
            object_ids["kpiSnapshot"] = oid
            time.sleep(0.5)
    if "kpiSnapshot" in object_ids:
        setup_kpi_snapshot(object_ids["kpiSnapshot"])

    # ── 15. AgentPerformanceMonthly ───────────────────────────────────────────
    if "agentPerformanceMonthly" in existing:
        print("\n► AgentPerformanceMonthly: ya existe")
        object_ids["agentPerformanceMonthly"] = existing["agentPerformanceMonthly"]
    else:
        print("\n► Creando objeto: AgentPerformanceMonthly")
        oid = create_object(
            name_singular="agentPerformanceMonthly",
            name_plural="agentPerformanceMonthly",
            label_singular="Desempeño Mensual Agente",
            label_plural="Desempeño Mensual Agentes",
            description="Snapshot mensual de productividad por agente: prima emitida, First Pass Yield, SLA y bono proyectado",
            icon="IconTrendingUp",
        )
        if oid:
            object_ids["agentPerformanceMonthly"] = oid
            time.sleep(0.5)
    if "agentPerformanceMonthly" in object_ids:
        setup_agent_performance_monthly(
            object_ids["agentPerformanceMonthly"],
            object_ids["agente"],
        )

    print(f"\n{'='*60}")
    print("  Setup completado.")
    print(f"  IDs de objetos creados: {json.dumps(object_ids, indent=2)}")
    print(f"{'='*60}\n")
    print("Próximos pasos:")
    print("  1. Abre http://localhost:3000 en tu navegador")
    print("  2. Ve a Settings → Data Model para verificar los objetos")
    print("  3. Crea las vistas por rol en Settings → Views")
    print()


if __name__ == "__main__":
    main()
