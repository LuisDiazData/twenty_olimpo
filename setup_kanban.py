#!/usr/bin/env python3
"""
Crea la vista Kanban "Mi pipeline" para el objeto Tramite.

- Tipo: KANBAN
- Agrupacion: estadoTramite
- Filtro: especialistaAsignado IS @Me
- Columnas Kanban: Pendiente → En revision → Listo para GNP → Enviado a GNP → Aprobado GNP / Rechazado GNP
- Columnas ocultas: Cerrado (no ensucian el board)
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
    "estadoTramite":        "98a522f0-65b7-4c6a-a2e5-3e799ffe22ea",  # SELECT — campo de agrupacion
    "especialistaAsignado": "9a79e477-5ff5-491f-b751-8dab1993d967",  # RELATION — filtro @Me
    "folioInterno":         "6a7f2cae-d65a-45ed-bef3-80b93b1879ab",
    "agenteTitular":        "d9df206e-7e9f-4633-8423-95c7af5e24ef",
    "tipoTramite":          "ab9353f7-d2b3-4f39-ad58-7c44e3815751",
    "ramo":                 "7196d098-0f53-4e85-a84d-e2619322329b",
    "fechaLimiteSla":       "13d6cae8-3a21-4f26-8d19-4463ac05b801",
    "nombreAsegurado":      "17a83965-385e-4792-8ff8-e8e2d39202a5",
    "fueraDeSla":           "9f94402c-c0cd-4a94-9ea4-168606464914",
}

# Columnas Kanban del board (fieldValue = valor SCREAMING_SNAKE_CASE del SELECT)
KANBAN_COLUMNS = [
    {"fieldValue": "PENDIENTE",      "label": "Pendiente",       "position": 0, "isVisible": True},
    {"fieldValue": "EN_REVISION",    "label": "En revision",     "position": 1, "isVisible": True},
    {"fieldValue": "LISTO_PARA_GNP", "label": "Listo para GNP", "position": 2, "isVisible": True},
    {"fieldValue": "ENVIADO_A_GNP",  "label": "Enviado a GNP",  "position": 3, "isVisible": True},
    {"fieldValue": "APROBADO_GNP",   "label": "Aprobado GNP",   "position": 4, "isVisible": True},
    {"fieldValue": "RECHAZADO_GNP",  "label": "Rechazado GNP",  "position": 5, "isVisible": True},
    {"fieldValue": "CERRADO",        "label": "Cerrado",         "position": 6, "isVisible": False},  # oculto
    {"fieldValue": "CANCELADO",      "label": "Cancelado",       "position": 7, "isVisible": False},  # oculto
    {"fieldValue": "",               "label": "Sin estado",      "position": 8, "isVisible": False},  # fallback
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
print("\n" + "="*60)
print("  SETUP KANBAN 'Mi pipeline' - Tramite")
print("="*60)

# ─── PASO 1: Verificar que no existe ─────────────────────────────────────────
print("\n[PASO 1] Vistas existentes en Tramite...")
r = gql(f'{{ getCoreViews(objectMetadataId: "{TRAMITE_OBJ_ID}") {{ id name type key position }} }}')
existing = r["data"]["getCoreViews"]
for v in existing:
    print(f"  [-] '{v['name']}' type={v['type']} pos={v['position']} id={v['id']}")

already = next((v for v in existing if "pipeline" in v["name"].lower() or "Pipeline" in v["name"]), None)
VIEW_ID = already["id"] if already else None
new_view = VIEW_ID is None

# ─── PASO 2: Crear la vista KANBAN ───────────────────────────────────────────
print("\n[PASO 2] Creando vista Kanban 'Mi pipeline'...")

if new_view:
    r = gql("""
mutation CreateView($input: CreateViewInput!) {
  createCoreView(input: $input) {
    id name type mainGroupByFieldMetadataId position visibility
  }
}""", {"input": {
        "name":                         "Mi pipeline",
        "objectMetadataId":             TRAMITE_OBJ_ID,
        "type":                         "KANBAN",
        "icon":                         "IconLayoutKanban",
        "visibility":                   "WORKSPACE",
        "position":                     2,
        "isCompact":                    False,
        "mainGroupByFieldMetadataId":   FIELDS["estadoTramite"],
        "shouldHideEmptyGroups":        False,
    }})

    if "errors" in r:
        log("!", f"Crear vista: {r['errors'][0]['message'][:100]}")
        exit(1)

    view = r["data"]["createCoreView"]
    VIEW_ID = view["id"]
    log("+", f"Vista Kanban '{view['name']}' creada — id={VIEW_ID}")
    log("+", f"Agrupada por estadoTramite — mainGroupByFieldMetadataId={view['mainGroupByFieldMetadataId']}")
else:
    log("-", f"Vista 'Mi pipeline' ya existe — id={VIEW_ID}")

# ─── PASO 3: Crear los grupos (columnas Kanban) ───────────────────────────────
print("\n[PASO 3] Creando columnas del Kanban...")

r = gql("""
mutation CreateGroups($inputs: [CreateViewGroupInput!]!) {
  createManyCoreViewGroups(inputs: $inputs) {
    id fieldValue position isVisible
  }
}""", {
    "inputs": [
        {
            "viewId":     VIEW_ID,
            "fieldValue": col["fieldValue"],
            "position":   col["position"],
            "isVisible":  col["isVisible"],
        }
        for col in KANBAN_COLUMNS
    ]
})

if "errors" in r:
    log("!", f"Grupos: {r['errors'][0]['message'][:100]}")
else:
    groups = r["data"]["createManyCoreViewGroups"]
    visible = [g for g in groups if g["isVisible"]]
    hidden  = [g for g in groups if not g["isVisible"]]
    log("+", f"{len(groups)} columnas creadas ({len(visible)} visibles, {len(hidden)} ocultas)")
    for g in sorted(visible, key=lambda x: x["position"]):
        label = next((c["label"] for c in KANBAN_COLUMNS if c["fieldValue"] == g["fieldValue"]), "?")
        print(f"     [{g['position']}] {label:20s} ({g['fieldValue']})")

# ─── PASO 4: Filtro @Me ───────────────────────────────────────────────────────
print("\n[PASO 4] Creando filtro 'Especialista asignado = @Me'...")

me_value = json.dumps({"isCurrentWorkspaceMemberSelected": True, "selectedRecordIds": []})

r = gql("""
mutation CreateFilter($input: CreateViewFilterInput!) {
  createCoreViewFilter(input: $input) {
    id fieldMetadataId operand value
  }
}""", {"input": {
    "fieldMetadataId": FIELDS["especialistaAsignado"],
    "operand":         "IS",
    "value":           me_value,
    "viewId":          VIEW_ID,
}})

if "errors" in r:
    log("!", f"Filtro: {r['errors'][0]['message'][:100]}")
else:
    f = r["data"]["createCoreViewFilter"]
    log("+", f"Filtro IS @Me en especialistaAsignado — id={f['id']}")

# ─── PASO 5: Campos visibles en las tarjetas ──────────────────────────────────
print("\n[PASO 5] Configurando campos visibles en las tarjetas...")

# En Kanban, los campos visibles aparecen dentro de cada tarjeta
card_fields = [
    {"fieldMetadataId": FIELDS["folioInterno"],    "isVisible": True,  "position": 0, "size": 160},
    {"fieldMetadataId": FIELDS["agenteTitular"],   "isVisible": True,  "position": 1, "size": 200},
    {"fieldMetadataId": FIELDS["ramo"],            "isVisible": True,  "position": 2, "size": 120},
    {"fieldMetadataId": FIELDS["tipoTramite"],     "isVisible": True,  "position": 3, "size": 160},
    {"fieldMetadataId": FIELDS["fechaLimiteSla"],  "isVisible": True,  "position": 4, "size": 150},
    {"fieldMetadataId": FIELDS["fueraDeSla"],      "isVisible": True,  "position": 5, "size": 110},
    {"fieldMetadataId": FIELDS["nombreAsegurado"], "isVisible": False, "position": 6, "size": 180},
]

r = gql("""
mutation CreateFields($inputs: [CreateViewFieldInput!]!) {
  createManyCoreViewFields(inputs: $inputs) {
    id fieldMetadataId isVisible position
  }
}""", {
    "inputs": [{**f, "viewId": VIEW_ID} for f in card_fields]
})

if "errors" in r:
    log("!", f"Campos: {r['errors'][0]['message'][:100]}")
else:
    fields = r["data"]["createManyCoreViewFields"]
    visible = sum(1 for f in fields if f["isVisible"])
    log("+", f"{len(fields)} campos de tarjeta configurados ({visible} visibles en la tarjeta)")

# ─── PASO 6: Verificacion final ───────────────────────────────────────────────
print("\n[PASO 6] Verificacion final...")

rv  = gql(f'{{ getCoreView(id: "{VIEW_ID}") {{ id name type mainGroupByFieldMetadataId visibility position }} }}')
rg  = gql(f'{{ getCoreViewGroups(viewId: "{VIEW_ID}") {{ fieldValue position isVisible }} }}')
rf  = gql(f'{{ getCoreViewFilters(viewId: "{VIEW_ID}") {{ fieldMetadataId operand value }} }}')

view_data   = rv["data"]["getCoreView"]
groups_data = sorted(rg["data"]["getCoreViewGroups"], key=lambda x: x["position"])
filter_data = rf["data"]["getCoreViewFilters"]

id_to_name = {v: k for k, v in FIELDS.items()}

print(f"\n  Vista: '{view_data['name']}' type={view_data['type']}")
print(f"  GroupBy: {id_to_name.get(view_data.get('mainGroupByFieldMetadataId',''), '?')}")
print(f"  Visibilidad: {view_data['visibility']}  Posicion: {view_data['position']}")

print(f"\n  Columnas Kanban ({sum(1 for g in groups_data if g['isVisible'])} visibles):")
for g in groups_data:
    label = next((c["label"] for c in KANBAN_COLUMNS if c["fieldValue"] == g["fieldValue"]), g["fieldValue"])
    visible_mark = "VISIBLE" if g["isVisible"] else "oculta"
    print(f"    [{g['position']}] {label:20s} — {visible_mark}")

print(f"\n  Filtros ({len(filter_data)}):")
for f in filter_data:
    fname = id_to_name.get(f["fieldMetadataId"], f["fieldMetadataId"][:8])
    val   = json.loads(f["value"]) if f["value"] else {}
    print(f"    {fname:25s}  {f['operand']}  @Me={val.get('isCurrentWorkspaceMemberSelected', False)}")

print("\n" + "="*60)
print("  RESUMEN")
print("="*60)
print(f"  [+] Exitosos: {ok}")
print(f"  [!] Fallidos: {fail}")
print(f"\n  Vista Kanban ID : {VIEW_ID}")
print(f"  URL             : http://localhost:3000/objects/tramites")
print()
print("  COMPORTAMIENTO:")
print("  - Cada especialista ve su pipeline personal (filtro @Me)")
print("  - Puede arrastrar tarjetas entre columnas para cambiar el estado")
print("  - Columnas activas: Pendiente → En revision → Listo GNP → Enviado → Aprobado / Rechazado")
print("  - Cerrado y Cancelado ocultos (limpian el board)")
print("="*60)
