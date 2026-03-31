#!/usr/bin/env python3
"""
Crea la vista "Mis tramites" para el objeto Tramite en Twenty CRM.

Vista: Mis tramites
- Filtro: especialistaAsignado IS @Me (usuario actual)
- Columnas: Folio, Agente titular, Tipo, Ramo, Estado, Fecha limite SLA
- Orden: Fecha limite SLA -> Ascendente
- Visibilidad: WORKSPACE (todos los miembros la ven)
- Posicion: 1 (despues de "All Tramites" que queda como INDEX)
"""
import json, urllib.request, urllib.error
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

ENDPOINT = os.getenv("TWENTY_API_URL", "http://localhost:3000") + "/metadata"
TOKEN    = "Bearer " + os.getenv("TWENTY_API_KEY", "")

# Object IDs
TRAMITE_OBJ_ID = "1c87eb5b-cd45-4c88-ac74-2456bdd9ad85"

# Field metadata IDs del objeto Tramite
FIELDS = {
    "name":                 "7df3cf3a-b757-4e23-bc19-1de52f017262",
    "folioInterno":         "6a7f2cae-d65a-45ed-bef3-80b93b1879ab",
    "agenteTitular":        "d9df206e-7e9f-4633-8423-95c7af5e24ef",  # RELATION
    "tipoTramite":          "ab9353f7-d2b3-4f39-ad58-7c44e3815751",  # SELECT
    "ramo":                 "7196d098-0f53-4e85-a84d-e2619322329b",  # SELECT
    "estadoTramite":        "98a522f0-65b7-4c6a-a2e5-3e799ffe22ea",  # SELECT
    "fechaLimiteSla":       "13d6cae8-3a21-4f26-8d19-4463ac05b801",  # DATE
    "especialistaAsignado": "9a79e477-5ff5-491f-b751-8dab1993d967",  # RELATION (para filtro)
    # Campos que deben estar ocultos (visible=False) en la nueva vista
    "fueraDeSla":           "9f94402c-c0cd-4a94-9ea4-168606464914",
    "fechaEntrada":         "2f6da908-bd37-4dad-a8e4-d288c3368b8f",
    "nombreAsegurado":      "17a83965-385e-4792-8ff8-e8e2d39202a5",
    "resultadoGnp":         "ee0b62c0-1788-4cbc-a403-fd8307b60afb",
    "numPolizaGnp":         "148311c4-ab52-4855-a4f6-1b6c56aa6dc9",
    "notasAnalista":        "3f5a83e4-9b8c-4c3d-acdc-4c3b24162768",
    "enviadoPor":           "c3879d08-5d43-4e60-9ad2-6649a820231c",
}

ok = 0; fail = 0

# ─── GQL helper ───────────────────────────────────────────────────────────────
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
print("\n" + "="*60)
print("  SETUP VISTA 'Mis tramites' - Tramite")
print("="*60)

# ─── PASO 1: Verificar que no existe ya ───────────────────────────────────────
print("\n[PASO 1] Verificando vistas existentes en Tramite...")
r = gql(f'{{ getCoreViews(objectMetadataId: "{TRAMITE_OBJ_ID}") {{ id name key position }} }}')
existing_views = r["data"]["getCoreViews"]
for v in existing_views:
    print(f"  [-] '{v['name']}' key={v['key']} pos={v['position']} id={v['id']}")

already_exists = next((v for v in existing_views if "Mis" in v["name"] or "mis" in v["name"].lower()), None)
if already_exists:
    print(f"  [-] Vista 'Mis tramites' ya existe: {already_exists['id']}")
    VIEW_ID = already_exists["id"]
    new_view = False
else:
    new_view = True

# ─── PASO 2: Crear la vista ───────────────────────────────────────────────────
print("\n[PASO 2] Creando vista 'Mis tramites'...")

CREATE_VIEW = """
mutation CreateView($input: CreateViewInput!) {
  createCoreView(input: $input) {
    id name type visibility position key
  }
}"""

if new_view:
    r = gql(CREATE_VIEW, {"input": {
        "name":             "Mis tramites",
        "objectMetadataId": TRAMITE_OBJ_ID,
        "type":             "TABLE",
        "icon":             "IconFileText",
        "visibility":       "WORKSPACE",
        "position":         1,
        "isCompact":        False,
    }})

    if "errors" in r:
        log("!", f"Crear vista: {r['errors'][0]['message'][:80]}")
        exit(1)

    view = r["data"]["createCoreView"]
    VIEW_ID = view["id"]
    log("+", f"Vista creada: '{view['name']}' id={VIEW_ID}")
else:
    log("-", f"Vista ya existe, usando id={VIEW_ID}")

# ─── PASO 3: Columnas visibles (ViewFields) ───────────────────────────────────
print("\n[PASO 3] Configurando columnas...")

CREATE_VIEW_FIELDS = """
mutation CreateViewFields($inputs: [CreateViewFieldInput!]!) {
  createManyCoreViewFields(inputs: $inputs) {
    id fieldMetadataId isVisible position size
  }
}"""

# Columnas que deben ser visibles con su posicion y ancho
visible_columns = [
    {"fieldMetadataId": FIELDS["folioInterno"],         "isVisible": True,  "position": 0, "size": 160},
    {"fieldMetadataId": FIELDS["agenteTitular"],        "isVisible": True,  "position": 1, "size": 200},
    {"fieldMetadataId": FIELDS["tipoTramite"],          "isVisible": True,  "position": 2, "size": 160},
    {"fieldMetadataId": FIELDS["ramo"],                 "isVisible": True,  "position": 3, "size": 120},
    {"fieldMetadataId": FIELDS["estadoTramite"],        "isVisible": True,  "position": 4, "size": 180},
    {"fieldMetadataId": FIELDS["fechaLimiteSla"],       "isVisible": True,  "position": 5, "size": 160},
]

# Columnas ocultas (existen en el objeto pero no se muestran en esta vista)
hidden_columns = [
    {"fieldMetadataId": FIELDS["fueraDeSla"],           "isVisible": False, "position": 6,  "size": 120},
    {"fieldMetadataId": FIELDS["fechaEntrada"],         "isVisible": False, "position": 7,  "size": 140},
    {"fieldMetadataId": FIELDS["nombreAsegurado"],      "isVisible": False, "position": 8,  "size": 180},
    {"fieldMetadataId": FIELDS["resultadoGnp"],         "isVisible": False, "position": 9,  "size": 150},
    {"fieldMetadataId": FIELDS["numPolizaGnp"],         "isVisible": False, "position": 10, "size": 150},
    {"fieldMetadataId": FIELDS["notasAnalista"],        "isVisible": False, "position": 11, "size": 180},
    {"fieldMetadataId": FIELDS["enviadoPor"],           "isVisible": False, "position": 12, "size": 160},
    {"fieldMetadataId": FIELDS["especialistaAsignado"], "isVisible": False, "position": 13, "size": 180},
]

all_columns = [
    {**col, "viewId": VIEW_ID}
    for col in visible_columns + hidden_columns
]

r = gql(CREATE_VIEW_FIELDS, {"inputs": all_columns})

if "errors" in r:
    log("!", f"Columnas: {r['errors'][0]['message'][:80]}")
else:
    created = r["data"]["createManyCoreViewFields"]
    visible_count = sum(1 for c in created if c["isVisible"])
    log("+", f"{len(created)} campos configurados ({visible_count} visibles, {len(created)-visible_count} ocultos)")

# ─── PASO 4: Filtro @Me en especialistaAsignado ───────────────────────────────
print("\n[PASO 4] Creando filtro 'Especialista asignado = @Me'...")

CREATE_FILTER = """
mutation CreateFilter($input: CreateViewFilterInput!) {
  createCoreViewFilter(input: $input) {
    id fieldMetadataId operand value viewId
  }
}"""

# El valor del filtro @Me para un campo RELATION segun el schema de Twenty:
# {"isCurrentWorkspaceMemberSelected": true, "selectedRecordIds": []}
me_filter_value = json.dumps({
    "isCurrentWorkspaceMemberSelected": True,
    "selectedRecordIds": []
})

r = gql(CREATE_FILTER, {"input": {
    "fieldMetadataId": FIELDS["especialistaAsignado"],
    "operand":         "IS",
    "value":           me_filter_value,
    "viewId":          VIEW_ID,
}})

if "errors" in r:
    log("!", f"Filtro: {r['errors'][0]['message'][:80]}")
else:
    f = r["data"]["createCoreViewFilter"]
    log("+", f"Filtro creado: especialistaAsignado IS @Me  id={f['id']}")

# ─── PASO 5: Ordenamiento por fechaLimiteSla ASC ──────────────────────────────
print("\n[PASO 5] Creando ordenamiento por 'Fecha limite SLA' ASC...")

CREATE_SORT = """
mutation CreateSort($input: CreateViewSortInput!) {
  createCoreViewSort(input: $input) {
    id fieldMetadataId direction viewId
  }
}"""

r = gql(CREATE_SORT, {"input": {
    "fieldMetadataId": FIELDS["fechaLimiteSla"],
    "direction":       "ASC",
    "viewId":          VIEW_ID,
}})

if "errors" in r:
    log("!", f"Ordenamiento: {r['errors'][0]['message'][:80]}")
else:
    s = r["data"]["createCoreViewSort"]
    log("+", f"Orden creado: fechaLimiteSla ASC  id={s['id']}")

# ─── PASO 6: Verificacion final ───────────────────────────────────────────────
print("\n[PASO 6] Verificacion final...")

r_fields  = gql(f'{{ getCoreViewFields(viewId: "{VIEW_ID}") {{ fieldMetadataId isVisible position size }} }}')
r_filters = gql(f'{{ getCoreViewFilters(viewId: "{VIEW_ID}") {{ id fieldMetadataId operand value }} }}')
r_sorts   = gql(f'{{ getCoreViewSorts(viewId: "{VIEW_ID}") {{ id fieldMetadataId direction }} }}')

fields_data  = r_fields["data"]["getCoreViewFields"]
filters_data = r_filters["data"]["getCoreViewFilters"]
sorts_data   = r_sorts["data"]["getCoreViewSorts"]

# Reverse lookup field IDs to names
id_to_name = {v: k for k, v in FIELDS.items()}

print(f"\n  Columnas visibles ({sum(1 for f in fields_data if f['isVisible'])}):")
for f in sorted([f for f in fields_data if f["isVisible"]], key=lambda x: x["position"]):
    fname = id_to_name.get(f["fieldMetadataId"], f["fieldMetadataId"][:8])
    print(f"    pos={f['position']}  {fname:25s}  size={f['size']}")

print(f"\n  Filtros ({len(filters_data)}):")
for f in filters_data:
    fname = id_to_name.get(f["fieldMetadataId"], f["fieldMetadataId"][:8])
    val = json.loads(f["value"]) if f["value"] else {}
    is_me = val.get("isCurrentWorkspaceMemberSelected", False)
    print(f"    {fname:25s}  {f['operand']}  @Me={is_me}")

print(f"\n  Ordenamiento ({len(sorts_data)}):")
for s in sorts_data:
    fname = id_to_name.get(s["fieldMetadataId"], s["fieldMetadataId"][:8])
    print(f"    {fname:25s}  {s['direction']}")

print("\n" + "="*60)
print("  RESUMEN")
print("="*60)
print(f"  [+] Exitosos: {ok}")
print(f"  [!] Fallidos: {fail}")
print(f"\n  Vista ID: {VIEW_ID}")
print(f"  URL: http://localhost:3000/objects/tramites  (tab 'Mis tramites')")
print()
print("  COMPORTAMIENTO:")
print("  - Cada usuario ve automaticamente solo SUS tramites")
print("  - Ordenados por fecha limite SLA (los mas urgentes primero)")
print("  - La vista es WORKSPACE: visible para todos los miembros")
print("  - @Me se resuelve al usuario logueado en cada sesion")
print("="*60)
