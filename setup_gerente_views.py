#!/usr/bin/env python3
"""
Crea 5 vistas TABLE para gerentes de ramo en el objeto Tramite.

Una vista por ramo: Vida, GMM, Autos, PYME, Danos.
- Filtro:  Ramo = <valor>
- Columnas: Folio, Agente titular, Tipo, Especialista asignado, Estado, Fecha limite SLA
- Agrupacion: Especialista asignado (gerente ve carga por analista)
- Visibilidad: WORKSPACE
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
    # Extra columnas ocultas (existen en objeto, no visibles en esta vista)
    "folioInterno_name":    "7df3cf3a-b757-4e23-bc19-1de52f017262",  # name (auto)
    "fueraDeSla":           "9f94402c-c0cd-4a94-9ea4-168606464914",
    "fechaEntrada":         "2f6da908-bd37-4dad-a8e4-d288c3368b8f",
    "nombreAsegurado":      "17a83965-385e-4792-8ff8-e8e2d39202a5",
    "resultadoGnp":         "ee0b62c0-1788-4cbc-a403-fd8307b60afb",
    "numPolizaGnp":         "148311c4-ab52-4855-a4f6-1b6c56aa6dc9",
    "notasAnalista":        "3f5a83e4-9b8c-4c3d-acdc-4c3b24162768",
    "enviadoPor":           "c3879d08-5d43-4e60-9ad2-6649a820231c",
}

# 5 ramos a crear
RAMOS = [
    {"value": "VIDA",  "label": "Vida",  "icon": "IconHeart",       "position": 3},
    {"value": "GMM",   "label": "GMM",   "icon": "IconStethoscope", "position": 4},
    {"value": "AUTOS", "label": "Autos", "icon": "IconCar",         "position": 5},
    {"value": "PYME",  "label": "PYME",  "icon": "IconBuildingStore","position": 6},
    {"value": "DANOS", "label": "Danos", "icon": "IconShield",      "position": 7},
]

# Columnas visibles (en orden) para las vistas de gerente
VISIBLE_COLS = [
    {"fieldMetadataId": FIELDS["folioInterno"],         "position": 0, "size": 150},
    {"fieldMetadataId": FIELDS["agenteTitular"],        "position": 1, "size": 200},
    {"fieldMetadataId": FIELDS["tipoTramite"],          "position": 2, "size": 160},
    {"fieldMetadataId": FIELDS["especialistaAsignado"], "position": 3, "size": 180},
    {"fieldMetadataId": FIELDS["estadoTramite"],        "position": 4, "size": 180},
    {"fieldMetadataId": FIELDS["fechaLimiteSla"],       "position": 5, "size": 160},
]

HIDDEN_COLS = [
    {"fieldMetadataId": FIELDS["ramo"],             "position": 6,  "size": 120},
    {"fieldMetadataId": FIELDS["fueraDeSla"],        "position": 7,  "size": 110},
    {"fieldMetadataId": FIELDS["fechaEntrada"],      "position": 8,  "size": 140},
    {"fieldMetadataId": FIELDS["nombreAsegurado"],   "position": 9,  "size": 180},
    {"fieldMetadataId": FIELDS["resultadoGnp"],      "position": 10, "size": 150},
    {"fieldMetadataId": FIELDS["numPolizaGnp"],      "position": 11, "size": 150},
    {"fieldMetadataId": FIELDS["notasAnalista"],     "position": 12, "size": 180},
    {"fieldMetadataId": FIELDS["enviadoPor"],        "position": 13, "size": 160},
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

# -----------------------------------------------------------------------------
print("\n" + "="*65)
print("  SETUP VISTAS DE GERENTE (5 ramos) - Tramite")
print("="*65)

# Verificar vistas existentes
r = gql(f'{{ getCoreViews(objectMetadataId: "{TRAMITE_OBJ_ID}") {{ id name type position }} }}')
existing = {v["name"]: v for v in r["data"]["getCoreViews"]}
print(f"\nVistas existentes: {len(existing)}")
for name, v in sorted(existing.items(), key=lambda x: x[1]["position"]):
    print(f"  [{v['position']}] {name:25s} ({v['type']})")

# --- Mutations ---------------------------------------------------------------
CREATE_VIEW = """
mutation CreateView($input: CreateViewInput!) {
  createCoreView(input: $input) { id name type position visibility mainGroupByFieldMetadataId }
}"""

CREATE_FIELDS = """
mutation CreateFields($inputs: [CreateViewFieldInput!]!) {
  createManyCoreViewFields(inputs: $inputs) { id fieldMetadataId isVisible position }
}"""

CREATE_FILTER = """
mutation CreateFilter($input: CreateViewFilterInput!) {
  createCoreViewFilter(input: $input) { id fieldMetadataId operand value }
}"""

# --- Crear vista por ramo ----------------------------------------------------
created_views = []

for ramo in RAMOS:
    view_name = f"Tramites {ramo['label']}"
    print(f"\n{'-'*65}")
    print(f"  RAMO: {ramo['label']}  ({view_name})")
    print(f"{'-'*65}")

    # Skip si ya existe
    if view_name in existing:
        vid = existing[view_name]["id"]
        log("-", f"Vista '{view_name}' ya existe (id={vid[:8]}), saltando")
        created_views.append({"name": view_name, "id": vid, "ramo": ramo["value"]})
        continue

    # 1. Crear la vista TABLE con agrupacion por especialistaAsignado
    r = gql(CREATE_VIEW, {"input": {
        "name":                       view_name,
        "objectMetadataId":           TRAMITE_OBJ_ID,
        "type":                       "TABLE",
        "icon":                       ramo["icon"],
        "visibility":                 "WORKSPACE",
        "position":                   ramo["position"],
        "isCompact":                  False,
        "mainGroupByFieldMetadataId": FIELDS["especialistaAsignado"],
    }})

    if "errors" in r:
        log("!", f"Crear vista '{view_name}': {r['errors'][0]['message'][:80]}")
        continue

    view = r["data"]["createCoreView"]
    VIEW_ID = view["id"]
    log("+", f"Vista '{view['name']}' creada — id={VIEW_ID[:8]}")
    created_views.append({"name": view_name, "id": VIEW_ID, "ramo": ramo["value"]})

    # 2. Columnas
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
        log("+", f"{len(created)} campos ({vis} visibles: Folio, Agente, Tipo, Especialista, Estado, SLA)")

    # 3. Filtro: ramo = <valor>
    # Para campos SELECT, el valor del filtro es JSON array de strings: '["VIDA"]'
    filter_value = json.dumps([ramo["value"]])

    r = gql(CREATE_FILTER, {"input": {
        "fieldMetadataId": FIELDS["ramo"],
        "operand":         "IS",
        "value":           filter_value,
        "viewId":          VIEW_ID,
    }})
    if "errors" in r:
        log("!", f"Filtro ramo={ramo['value']}: {r['errors'][0]['message'][:80]}")
    else:
        f = r["data"]["createCoreViewFilter"]
        log("+", f"Filtro 'Ramo IS {ramo['value']}' creado — id={f['id'][:8]}")

# --- Verificacion final -------------------------------------------------------
print(f"\n{'='*65}")
print("  VERIFICACION FINAL")
print(f"{'='*65}")

r = gql(f'{{ getCoreViews(objectMetadataId: "{TRAMITE_OBJ_ID}") {{ id name type position visibility mainGroupByFieldMetadataId }} }}')
all_views = sorted(r["data"]["getCoreViews"], key=lambda x: x["position"])

print(f"\n  Total vistas en Tramite: {len(all_views)}")
for v in all_views:
    group_field = "especialistaAsignado" if v.get("mainGroupByFieldMetadataId") == FIELDS["especialistaAsignado"] else (
                  "estadoTramite" if v.get("mainGroupByFieldMetadataId") == FIELDS["estadoTramite"] else "—")
    print(f"  [{v['position']}] {v['name']:25s} {v['type']:8s}  grupo={group_field}")

print(f"\n  Vistas creadas en esta ejecucion:")
for cv in created_views:
    # Get filter info
    r2 = gql(f'{{ getCoreViewFilters(viewId: "{cv["id"]}") {{ fieldMetadataId operand value }} }}')
    filters = r2["data"]["getCoreViewFilters"]
    filter_desc = ", ".join(
        f"ramo IS {json.loads(f['value'])[0] if f['value'] else '?'}"
        for f in filters if f["fieldMetadataId"] == FIELDS["ramo"]
    ) or "sin filtro"
    print(f"    {cv['name']:25s}  filtro: {filter_desc}")

print(f"\n{'='*65}")
print("  RESUMEN")
print(f"{'='*65}")
print(f"  [+] Exitosos: {ok}")
print(f"  [!] Fallidos: {fail}")
print()
print("  COMPORTAMIENTO PARA GERENTES:")
print("  - Cada gerente ve SOLO los tramites de su ramo (filtro SELECT)")
print("  - Los tramites aparecen AGRUPADOS por Especialista asignado")
print("  - De un vistazo: cuantos tramites tiene cada analista en su ramo")
print("  - Columnas: Folio / Agente / Tipo / Especialista / Estado / SLA")
print(f"{'='*65}")
