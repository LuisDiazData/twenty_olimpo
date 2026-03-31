#!/usr/bin/env python3
"""
Setup completo del modelo de datos de la promotoria GNP en Twenty CRM.
Usa la GraphQL Metadata API en http://localhost:3000/metadata
"""

import json
import urllib.request
import urllib.error
import unicodedata
import re
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

ENDPOINT     = os.getenv("TWENTY_API_URL", "http://localhost:3000") + "/metadata"
TOKEN        = "Bearer " + os.getenv("TWENTY_API_KEY", "")
WS_MEMBER_ID = os.getenv("TWENTY_WS_MEMBER_ID", "c312bc10-4a79-4fa7-8e2b-ffeddd1b8704")

COLORS = ["sky","green","blue","purple","turquoise","pink","red","orange","yellow","gray"]
summary = {"created": [], "skipped": [], "failed": []}

# ─── GQL helper ──────────────────────────────────────────────────────────────

def gql(query, variables=None):
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req  = urllib.request.Request(
        ENDPOINT, data=body,
        headers={"Authorization": TOKEN, "Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())

# ─── Utilities ────────────────────────────────────────────────────────────────

def to_value(label: str) -> str:
    """Convert 'Nueva póliza' → 'NUEVA_POLIZA'"""
    nfkd = unicodedata.normalize("NFKD", label)
    ascii_str = nfkd.encode("ASCII", "ignore").decode()
    value = re.sub(r"[^A-Z0-9]+", "_", ascii_str.upper()).strip("_")
    return value or "OPTION"

def options(labels):
    return [
        {"value": to_value(l), "label": l, "position": i, "color": COLORS[i % len(COLORS)]}
        for i, l in enumerate(labels)
    ]

def log(status, msg):
    icons = {"OK": "+", "SKIP": "-", "ERR": "!"}
    print(f"  [{icons.get(status, status)}] {msg}")
    summary[{"OK":"created","SKIP":"skipped","ERR":"failed"}[status]].append(msg)

# ─── Fetch existing state ─────────────────────────────────────────────────────

def load_state():
    """Returns (objects_by_name, fields_by_obj_name)"""
    r = gql("""{
      objects(paging:{first:60}){
        edges{ node{ id nameSingular labelSingular isCustom
          fields(paging:{first:100}){
            edges{ node{ id name type isActive } }
          }
        }}
      }
    }""")
    objects_by_name = {}
    fields_by_obj  = {}
    for e in r["data"]["objects"]["edges"]:
        o = e["node"]
        objects_by_name[o["nameSingular"]] = o
        fields_by_obj[o["nameSingular"]] = {
            f["node"]["name"]: f["node"]
            for f in o["fields"]["edges"]
        }
    return objects_by_name, fields_by_obj

# ─── Create helpers ───────────────────────────────────────────────────────────

CREATE_OBJECT = """
mutation CreateOneObject($input: CreateOneObjectInput!) {
  createOneObject(input: $input) { id nameSingular labelSingular }
}"""

CREATE_FIELD = """
mutation CreateOneField($input: CreateOneFieldMetadataInput!) {
  createOneField(input: $input) { id name type label }
}"""

def create_object(name_singular, name_plural, label_singular, label_plural,
                  description="", icon="IconBox"):
    r = gql(CREATE_OBJECT, {"input": {"object": {
        "nameSingular": name_singular, "namePlural": name_plural,
        "labelSingular": label_singular, "labelPlural": label_plural,
        "description": description, "icon": icon
    }}})
    if "errors" in r or not r.get("data",{}).get("createOneObject"):
        err = r.get("errors", r.get("error","?"))
        log("ERR", f"create object '{name_singular}': {str(err)[:100]}")
        return None
    obj = r["data"]["createOneObject"]
    log("OK", f"object '{label_singular}' id={obj['id']}")
    return obj["id"]

def create_field(obj_id, obj_name, field_name, field_type, label,
                 opts=None, default=None, relation_payload=None):
    payload = {
        "objectMetadataId": obj_id,
        "type": field_type,
        "name": field_name,
        "label": label,
        "isNullable": True,
    }
    if opts:
        payload["options"] = opts
    if default is not None:
        payload["defaultValue"] = default
    if relation_payload:
        payload["relationCreationPayload"] = relation_payload

    r = gql(CREATE_FIELD, {"input": {"field": payload}})

    if "errors" in r:
        msgs = [e.get("message","") for e in r["errors"]]
        if any("already exists" in m.lower() or "duplicate" in m.lower() or "unique" in m.lower() for m in msgs):
            log("SKIP", f"{obj_name}.{field_name} (already exists)")
        else:
            log("ERR",  f"{obj_name}.{field_name}: {msgs[0][:80]}")
        return None

    f = r.get("data",{}).get("createOneField")
    if not f:
        err = r.get("error", str(r)[:80])
        # Check for duplicate-style error in non-standard response
        if "already" in str(err).lower() or "duplicate" in str(err).lower():
            log("SKIP", f"{obj_name}.{field_name} (already exists)")
        else:
            log("ERR",  f"{obj_name}.{field_name}: {err}")
        return None

    log("OK", f"{obj_name}.{field_name} ({field_type}) id={f['id']}")
    return f["id"]

def relation(from_id, to_id, from_name, to_name, from_label, to_label,
             from_icon="IconLink", to_icon="IconLink"):
    """Creates MANY_TO_ONE relation: from_obj.from_name → to_obj"""
    return create_field(
        from_id, from_name, from_name, "RELATION", from_label,
        relation_payload={
            "type": "MANY_TO_ONE",
            "targetObjectMetadataId": to_id,
            "targetFieldLabel": to_label,
            "targetFieldIcon": to_icon,
        }
    )

# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════

print("\n" + "="*60)
print("  SETUP MODELO PROMOTORIA GNP - Twenty CRM")
print("="*60)

print("\n[PASO 1] Cargando estado actual...")
OBJ, FIELDS = load_state()
print(f"  Objetos encontrados: {len(OBJ)}")
for n, o in OBJ.items():
    tag = "[C]" if o["isCustom"] else "[S]"
    print(f"    {tag} {n:35s} id={o['id']}")

COMPANY_ID    = OBJ["company"]["id"]
PERSON_ID     = OBJ["person"]["id"]

# ─── PASO 2 — Campos en Company (Agente) ─────────────────────────────────────
print("\n[PASO 2] Campos en Company (Agente)...")

existing = FIELDS.get("company", {})

COMPANY_FIELDS = [
    ("cua",              "TEXT",         "CUA",                    None),
    ("tipoAgente",       "SELECT",       "Tipo de agente",
        options(["Individual","Con asistentes","Despacho formal"])),
    ("rfc",              "TEXT",         "RFC",                    None),
    ("ramosPrincipal",   "MULTI_SELECT", "Ramo principal",
        options(["Vida","GMM","Autos","PYME","Daños"])),
    ("estatusAgente",    "SELECT",       "Estatus",
        options(["Activo","Inactivo"])),
    ("fechaIncorporacion","DATE",        "Fecha incorporación",    None),
    ("promotoria",       "TEXT",         "Promotoría",             None),
    ("notasInternas",    "TEXT",         "Notas internas",         None),
]

for fname, ftype, flabel, fopts in COMPANY_FIELDS:
    if fname in existing:
        log("SKIP", f"company.{fname} (already exists)")
        continue
    create_field(COMPANY_ID, "company", fname, ftype, flabel, opts=fopts)

# ─── PASO 3 — Campos en Person (Contacto) ────────────────────────────────────
print("\n[PASO 3] Campos en Person (Contacto)...")

existing = FIELDS.get("person", {})

PERSON_FIELDS = [
    ("rolContacto",    "SELECT",  "Rol",
        options(["Titular","Asistente"])),
    ("email2",         "TEXT",    "Email 2",       None),
    ("telefono2",      "TEXT",    "Teléfono 2",    None),
    ("whatsapp",       "TEXT",    "WhatsApp",      None),
    ("contactoActivo", "BOOLEAN", "Activo",        None),
]

for fname, ftype, flabel, fopts in PERSON_FIELDS:
    if fname in existing:
        log("SKIP", f"person.{fname} (already exists)")
        continue
    create_field(PERSON_ID, "person", fname, ftype, flabel, opts=fopts)

# ─── PASO 4 — Objeto: Asignación ─────────────────────────────────────────────
print("\n[PASO 4] Objeto Asignación...")

if "asignacion" in OBJ:
    log("SKIP", "object 'asignacion' (already exists)")
    ASIG_ID = OBJ["asignacion"]["id"]
else:
    ASIG_ID = create_object(
        "asignacion","asignaciones","Asignación","Asignaciones",
        "Relación entre agente, ramo y especialista asignado","IconLink"
    )

if ASIG_ID:
    OBJ, FIELDS = load_state()   # reload to get new fields
    existing = FIELDS.get("asignacion", {})

    for fname, ftype, flabel, fopts in [
        ("ramo",            "SELECT",  "Ramo",        options(["Vida","GMM","Autos","PYME","Daños"])),
        ("asignacionActiva","BOOLEAN", "Activa",      None),
        ("fechaDesde",      "DATE",    "Fecha desde", None),
    ]:
        if fname in existing: log("SKIP", f"asignacion.{fname}"); continue
        create_field(ASIG_ID, "asignacion", fname, ftype, flabel, opts=fopts)

    # Relaciones
    if "agente" not in existing:
        relation(ASIG_ID, COMPANY_ID,  "agente",      "asignaciones",
                 "Agente",      "Asignaciones","IconUserCircle","IconLink")
    else:
        log("SKIP","asignacion.agente (already exists)")

    if "especialista" not in existing:
        relation(ASIG_ID, WS_MEMBER_ID, "especialista","asignacionesComoEspecialista",
                 "Especialista","Asignaciones","IconUserStar","IconLink")
    else:
        log("SKIP","asignacion.especialista (already exists)")

# ─── PASO 5 — Objeto: Trámite ─────────────────────────────────────────────────
print("\n[PASO 5] Objeto Trámite...")

if "tramite" in OBJ:
    log("SKIP", "object 'tramite' (already exists)")
    TRAM_ID = OBJ["tramite"]["id"]
else:
    TRAM_ID = create_object(
        "tramite","tramites","Trámite","Trámites",
        "Trámite enviado por agente a la promotoría para envío a GNP","IconFileText"
    )

if TRAM_ID:
    OBJ, FIELDS = load_state()
    existing = FIELDS.get("tramite", {})

    TRAMITE_FIELDS = [
        ("folioInterno",    "TEXT",    "Folio",             None),
        ("tipoTramite",     "SELECT",  "Tipo de trámite",
            options(["Nueva póliza","Endoso","Renovación","Cancelación","Siniestro","Cotización PYME"])),
        ("ramo",            "SELECT",  "Ramo",
            options(["Vida","GMM","Autos","PYME","Daños"])),
        ("estadoTramite",   "SELECT",  "Estado",
            options(["Pendiente","En revisión","Listo para GNP","Enviado a GNP",
                     "Aprobado GNP","Rechazado GNP","Cerrado"])),
        ("resultadoGnp",    "SELECT",  "Resultado GNP",
            options(["Pendiente","Aprobado","Rechazado"])),
        ("fechaEntrada",    "DATE",    "Fecha entrada",     None),
        ("fechaLimiteSla",  "DATE",    "Fecha límite SLA",  None),
        ("fueraDeSla",      "BOOLEAN", "Fuera de SLA",      None),
        ("nombreAsegurado", "TEXT",    "Nombre asegurado",  None),
        ("numPolizaGnp",    "TEXT",    "No. póliza GNP",    None),
        ("notasAnalista",   "TEXT",    "Notas analista",    None),
    ]
    for fname, ftype, flabel, fopts in TRAMITE_FIELDS:
        if fname in existing: log("SKIP", f"tramite.{fname}"); continue
        create_field(TRAM_ID, "tramite", fname, ftype, flabel, opts=fopts)

    # Relaciones
    if "agenteTitular" not in existing:
        relation(TRAM_ID, COMPANY_ID,   "agenteTitular",  "tramitesTitular",
                 "Agente titular","Trámites (titular)","IconUserCircle","IconFileText")
    else:
        log("SKIP","tramite.agenteTitular")

    if "enviadoPor" not in existing:
        relation(TRAM_ID, PERSON_ID,    "enviadoPor",     "tramitesEnviados",
                 "Enviado por","Trámites enviados","IconUser","IconFileText")
    else:
        log("SKIP","tramite.enviadoPor")

    if "especialistaAsignado" not in existing:
        relation(TRAM_ID, WS_MEMBER_ID, "especialistaAsignado","tramitesAsignados",
                 "Especialista asignado","Trámites asignados","IconUserStar","IconFileText")
    else:
        log("SKIP","tramite.especialistaAsignado")

# ─── PASO 6 — Objeto: Documento ──────────────────────────────────────────────
print("\n[PASO 6] Objeto Documento...")

if "documento" in OBJ:
    log("SKIP", "object 'documento' (already exists)")
    DOC_ID = OBJ["documento"]["id"]
else:
    DOC_ID = create_object(
        "documento","documentos","Documento","Documentos",
        "Documento adjunto a un trámite","IconPaperclip"
    )

if DOC_ID:
    OBJ, FIELDS = load_state()
    existing = FIELDS.get("documento", {})
    TRAM_ID   = TRAM_ID or OBJ.get("tramite",{}).get("id")

    for fname, ftype, flabel, fopts in [
        ("tipoDocumento", "SELECT", "Tipo",
            options(["INE","Acta nacimiento","Comprobante domicilio","Recibo pago",
                     "Solicitud firmada","Carátula póliza","Otro"])),
        ("estadoDoc",     "SELECT", "Estado",
            options(["Recibido","Falta","Rechazado"])),
        ("notasDoc",      "TEXT",   "Notas",      None),
        ("fechaRecepcion","DATE",   "Fecha recepción", None),
    ]:
        if fname in existing: log("SKIP", f"documento.{fname}"); continue
        create_field(DOC_ID, "documento", fname, ftype, flabel, opts=fopts)

    if "tramite" not in existing and TRAM_ID:
        relation(DOC_ID, TRAM_ID, "tramite", "documentos",
                 "Trámite","Documentos","IconFileText","IconPaperclip")
    else:
        log("SKIP","documento.tramite")

# ─── PASO 7 — Objeto: Razón de Rechazo ───────────────────────────────────────
print("\n[PASO 7] Objeto Razón de Rechazo...")

if "razonRechazo" in OBJ:
    log("SKIP", "object 'razonRechazo' (already exists)")
    RECH_ID = OBJ["razonRechazo"]["id"]
else:
    RECH_ID = create_object(
        "razonRechazo","razonesRechazo","Razón de rechazo","Razones de rechazo",
        "Motivos de rechazo de trámites","IconAlertTriangle"
    )

if RECH_ID:
    OBJ, FIELDS = load_state()
    existing = FIELDS.get("razonRechazo", {})
    TRAM_ID   = TRAM_ID or OBJ.get("tramite",{}).get("id")

    for fname, ftype, flabel, fopts in [
        ("categoria",   "SELECT", "Categoría",
            options(["Documentación incompleta","Datos incorrectos","Fuera de perfil",
                     "Error de captura","Firma faltante","Otro"])),
        ("descripcion", "TEXT",   "Descripción", None),
        ("frecuencia",  "NUMBER", "Frecuencia",  None),
    ]:
        if fname in existing: log("SKIP", f"razonRechazo.{fname}"); continue
        create_field(RECH_ID, "razonRechazo", fname, ftype, flabel, opts=fopts)

    if "tramite" not in existing and TRAM_ID:
        relation(RECH_ID, TRAM_ID, "tramite", "razonesRechazo",
                 "Trámite","Razones de rechazo","IconFileText","IconAlertTriangle")
    else:
        log("SKIP","razonRechazo.tramite")

# ─── RESUMEN ──────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("  RESUMEN")
print("="*60)
print(f"  [+] Creados:  {len(summary['created'])}")
print(f"  [-] Saltados: {len(summary['skipped'])}")
print(f"  [!] Fallidos: {len(summary['failed'])}")

if summary["failed"]:
    print("\n  FALLIDOS:")
    for f in summary["failed"]:
        print(f"    - {f}")

# ─── ID MAP ───────────────────────────────────────────────────────────────────
OBJ_FINAL, _ = load_state()
id_map = {
    "agente_id":        OBJ_FINAL.get("company",{}).get("id",""),
    "contacto_id":      OBJ_FINAL.get("person",{}).get("id",""),
    "asignacion_id":    OBJ_FINAL.get("asignacion",{}).get("id",""),
    "tramite_id":       OBJ_FINAL.get("tramite",{}).get("id",""),
    "documento_id":     OBJ_FINAL.get("documento",{}).get("id",""),
    "razon_rechazo_id": OBJ_FINAL.get("razonRechazo",{}).get("id",""),
    "workspace_member_id": WS_MEMBER_ID,
}
print("\n  ID MAP:")
print(json.dumps(id_map, indent=4))

with open("C:/Users/wichi/twenty_id_map.json", "w") as f:
    json.dump(id_map, f, indent=4)
print("\n  Guardado en C:/Users/wichi/twenty_id_map.json")
