#!/usr/bin/env python3
"""
Crea 5 vistas "SLA vencido — <Ramo>" para cada gerente.

Filtros combinados (AND implicito):
  1. Ramo = <valor>       (SELECT IS)
  2. Fuera de SLA = true  (BOOLEAN IS)

Orden: Fecha limite SLA ASC (los mas urgentes primero)
Columnas: Folio, Agente titular, Tipo, Especialista asignado, Estado, SLA

Logica AND: en Twenty, multiples filtros sin viewFilterGroupId
se combinan con AND de forma automatica.
"""
import json, urllib.request, urllib.error
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

ENDPOINT = os.getenv("TWENTY_API_URL", "http://localhost:3000") + "/metadata"
TOKEN    = "Bearer " + os.getenv("TWENTY_API_KEY", "")

TRAMITE_OBJ_ID = "1c87eb5b-cd45-4c88-ac74-2456bdd9ad85"

FIELDS = {
    "folioInterno":         "6a7f2cae-d65a-45ed-bef3-80b93b1879ab",
    "agenteTitular":        "d9df206e-7e9f-4633-8423-95c7af5e24ef",
    "tipoTramite":          "ab9353f7-d2b3-4f39-ad58-7c44e3815751",
    "especialistaAsignado": "9a79e477-5ff5-491f-b751-8dab1993d967",
    "estadoTramite":        "98a522f0-65b7-4c6a-a2e5-3e799ffe22ea",
    "fechaLimiteSla":       "13d6cae8-3a21-4f26-8d19-4463ac05b801",
    "ramo":                 "7196d098-0f53-4e85-a84d-e2619322329b",
    "fueraDeSla":           "9f94402c-c0cd-4a94-9ea4-168606464914",
    # ocultos
    "fechaEntrada":         "2f6da908-bd37-4dad-a8e4-d288c3368b8f",
    "nombreAsegurado":      "17a83965-385e-4792-8ff8-e8e2d39202a5",
    "resultadoGnp":         "ee0b62c0-1788-4cbc-a403-fd8307b60afb",
    "numPolizaGnp":         "148311c4-ab52-4855-a4f6-1b6c56aa6dc9",
    "notasAnalista":        "3f5a83e4-9b8c-4c3d-acdc-4c3b24162768",
    "enviadoPor":           "c3879d08-5d43-4e60-9ad2-6649a820231c",
}

RAMOS = [
    {"value": "VIDA",  "label": "Vida",  "icon": "IconAlertHeart",      "position": 8},
    {"value": "GMM",   "label": "GMM",   "icon": "IconAlertCircle",     "position": 9},
    {"value": "AUTOS", "label": "Autos", "icon": "IconAlertTriangle",   "position": 10},
    {"value": "PYME",  "label": "PYME",  "icon": "IconAlertSquare",     "position": 11},
    {"value": "DANOS", "label": "Danos", "icon": "IconAlertOctagon",    "position": 12},
]

# Columnas visibles — igual que gerente pero con fueraDeSla al frente como indicador
VISIBLE_COLS = [
    {"fieldMetadataId": FIELDS["fueraDeSla"],           "position": 0, "size": 110},  # indicador de alerta
    {"fieldMetadataId": FIELDS["fechaLimiteSla"],       "position": 1, "size": 150},  # primero para ver urgencia
    {"fieldMetadataId": FIELDS["folioInterno"],         "position": 2, "size": 140},
    {"fieldMetadataId": FIELDS["agenteTitular"],        "position": 3, "size": 190},
    {"fieldMetadataId": FIELDS["tipoTramite"],          "position": 4, "size": 150},
    {"fieldMetadataId": FIELDS["especialistaAsignado"], "position": 5, "size": 180},
    {"fieldMetadataId": FIELDS["estadoTramite"],        "position": 6, "size": 170},
]

HIDDEN_COLS = [
    {"fieldMetadataId": FIELDS["ramo"],          "position": 7,  "size": 120},
    {"fieldMetadataId": FIELDS["fechaEntrada"],  "position": 8,  "size": 140},
    {"fieldMetadataId": FIELDS["nombreAsegurado"],"position": 9, "size": 180},
    {"fieldMetadataId": FIELDS["resultadoGnp"],  "position": 10, "size": 150},
    {"fieldMetadataId": FIELDS["numPolizaGnp"],  "position": 11, "size": 150},
    {"fieldMetadataId": FIELDS["notasAnalista"], "position": 12, "size": 180},
    {"fieldMetadataId": FIELDS["enviadoPor"],    "position": 13, "size": 160},
]

ok = 0; fail = 0

def gql(query, variables=None):
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req  = urllib.request.Request(ENDPOINT, data=body,
             headers={"Authorization": TOKEN, "Content-Type": "application/json"},
             method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())

def log(status, msg):
    global ok, fail
    icons = {"+": "[+]", "-": "[-]", "!": "[!]"}
    print(f"  {icons.get(status,'[?]')} {msg}")
    if status == "+": ok += 1
    elif status == "!": fail += 1

# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*65)
print("  SETUP VISTAS 'SLA vencido' (5 ramos) - Tramite")
print("="*65)

# Vistas existentes
r = gql(f'{{ getCoreViews(objectMetadataId: "{TRAMITE_OBJ_ID}") {{ id name type position }} }}')
existing = {v["name"]: v for v in r["data"]["getCoreViews"]}
print(f"\nVistas existentes: {len(existing)}")
for name, v in sorted(existing.items(), key=lambda x: x[1]["position"]):
    print(f"  [{v['position']}] {name}")

# GQL mutations
CREATE_VIEW = """
mutation CreateView($input: CreateViewInput!) {
  createCoreView(input: $input) { id name type position }
}"""

CREATE_FIELDS = """
mutation CreateFields($inputs: [CreateViewFieldInput!]!) {
  createManyCoreViewFields(inputs: $inputs) { id fieldMetadataId isVisible position }
}"""

CREATE_FILTER = """
mutation CreateFilter($input: CreateViewFilterInput!) {
  createCoreViewFilter(input: $input) { id fieldMetadataId operand value }
}"""

CREATE_SORT = """
mutation CreateSort($input: CreateViewSortInput!) {
  createCoreViewSort(input: $input) { id fieldMetadataId direction }
}"""

created_views = []

for ramo in RAMOS:
    view_name = f"SLA vencido - {ramo['label']}"
    print(f"\n{'='*65}")
    print(f"  {view_name}")
    print(f"{'='*65}")

    if view_name in existing:
        vid = existing[view_name]["id"]
        log("-", f"Ya existe (id={vid[:8]}), saltando")
        created_views.append({"name": view_name, "id": vid, "ramo": ramo["value"]})
        continue

    # ── 1. Crear vista TABLE ──────────────────────────────────────────────────
    r = gql(CREATE_VIEW, {"input": {
        "name":             view_name,
        "objectMetadataId": TRAMITE_OBJ_ID,
        "type":             "TABLE",
        "icon":             ramo["icon"],
        "visibility":       "WORKSPACE",
        "position":         ramo["position"],
        "isCompact":        False,
    }})
    if "errors" in r:
        log("!", f"Crear vista: {r['errors'][0]['message'][:80]}")
        continue

    VIEW_ID = r["data"]["createCoreView"]["id"]
    log("+", f"Vista creada — id={VIEW_ID[:8]}")
    created_views.append({"name": view_name, "id": VIEW_ID, "ramo": ramo["value"]})

    # ── 2. Columnas ───────────────────────────────────────────────────────────
    all_cols = (
        [{**c, "isVisible": True,  "viewId": VIEW_ID} for c in VISIBLE_COLS] +
        [{**c, "isVisible": False, "viewId": VIEW_ID} for c in HIDDEN_COLS]
    )
    r = gql(CREATE_FIELDS, {"inputs": all_cols})
    if "errors" in r:
        log("!", f"Columnas: {r['errors'][0]['message'][:80]}")
    else:
        created = r["data"]["createManyCoreViewFields"]
        vis = sum(1 for c in created if c["isVisible"])
        log("+", f"{len(created)} campos ({vis} visibles: FueraSLA, FechaSLA, Folio, Agente, Tipo, Esp, Estado)")

    # ── 3. Filtro 1: Ramo = <valor>  (SELECT IS) ─────────────────────────────
    # Valor del filtro SELECT: JSON array de strings => '["VIDA"]'
    r = gql(CREATE_FILTER, {"input": {
        "fieldMetadataId": FIELDS["ramo"],
        "operand":         "IS",
        "value":           json.dumps([ramo["value"]]),  # '["VIDA"]'
        "viewId":          VIEW_ID,
    }})
    if "errors" in r:
        log("!", f"Filtro ramo: {r['errors'][0]['message'][:80]}")
    else:
        f = r["data"]["createCoreViewFilter"]
        log("+", f"Filtro 1: Ramo IS {ramo['value']}  id={f['id'][:8]}")

    # ── 4. Filtro 2: Fuera de SLA = true  (BOOLEAN IS) ───────────────────────
    # Para BOOLEAN, Twenty evalua: recordFilter.value === 'true'
    # -> almacenar el string "true" como valor JSON
    r = gql(CREATE_FILTER, {"input": {
        "fieldMetadataId": FIELDS["fueraDeSla"],
        "operand":         "IS",
        "value":           "true",   # JSON string (no boolean)
        "viewId":          VIEW_ID,
    }})
    if "errors" in r:
        log("!", f"Filtro fueraDeSla: {r['errors'][0]['message'][:80]}")
    else:
        f = r["data"]["createCoreViewFilter"]
        log("+", f"Filtro 2: FueraDeSla IS true  id={f['id'][:8]}")

    # ── 5. Ordenamiento: Fecha limite SLA ASC ────────────────────────────────
    r = gql(CREATE_SORT, {"input": {
        "fieldMetadataId": FIELDS["fechaLimiteSla"],
        "direction":       "ASC",
        "viewId":          VIEW_ID,
    }})
    if "errors" in r:
        log("!", f"Sort: {r['errors'][0]['message'][:80]}")
    else:
        s = r["data"]["createCoreViewSort"]
        log("+", f"Orden: fechaLimiteSla ASC  id={s['id'][:8]}")

# ─── Verificacion final ───────────────────────────────────────────────────────
print(f"\n{'='*65}")
print("  VERIFICACION FINAL")
print(f"{'='*65}")

r = gql(f'{{ getCoreViews(objectMetadataId: "{TRAMITE_OBJ_ID}") {{ id name type position }} }}')
all_views = sorted(r["data"]["getCoreViews"], key=lambda x: x["position"])
print(f"\n  Total vistas en Tramite: {len(all_views)}")
for v in all_views:
    print(f"  [{v['position']:2d}] {v['name']}")

print(f"\n  Detalle de vistas SLA creadas:")
for cv in created_views:
    r2 = gql(f'{{ getCoreViewFilters(viewId: "{cv["id"]}") {{ fieldMetadataId operand value }} getCoreViewSorts(viewId: "{cv["id"]}") {{ fieldMetadataId direction }} }}')
    filters = r2["data"]["getCoreViewFilters"]
    sorts   = r2["data"]["getCoreViewSorts"]
    filter_desc = " AND ".join(
        f"ramo=={json.loads(f['value'])[0]}" if f["fieldMetadataId"] == FIELDS["ramo"]
        else f"fueraDeSla=={f['value']}"
        for f in filters
    )
    sort_desc = ", ".join(f"fechaSLA {s['direction']}" for s in sorts)
    print(f"\n    {cv['name']}")
    print(f"      filtros:  {filter_desc}")
    print(f"      orden:    {sort_desc or '—'}")

print(f"\n{'='*65}")
print("  RESUMEN")
print(f"{'='*65}")
print(f"  [+] Exitosos: {ok}")
print(f"  [!] Fallidos: {fail}")
print()
print("  COMPORTAMIENTO:")
print("  - Vista de alarma diaria del gerente")
print("  - Solo muestra tramites de su ramo con SLA vencido")
print("  - Ordenados por fecha SLA: el mas urgente primero")
print("  - Columna 'Fuera de SLA' visible al frente como indicador rojo")
print("  - AND implicito: ambos filtros deben cumplirse")
print(f"{'='*65}")
