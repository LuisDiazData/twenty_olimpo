#!/usr/bin/env python3
"""
Crea 3 vistas globales para la directora en el objeto Tramite.

1. Todos los ramos      - Sin filtro, agrupa por Ramo (SELECT)
2. SLA global           - Filtro: fueraDeSla = true, agrupa por Ramo
3. Rechazos GNP         - Filtro: resultadoGnp = RECHAZADO, agrupa por RazonRechazo (RELATION)

La vista de Rechazos agrupada por razon es el "momento wow" del demo:
la directora ve de un vistazo cual es el error mas comun de los agentes.
"""
import json, urllib.request, urllib.error

ENDPOINT = "http://localhost:3000/metadata"
TOKEN = ("Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
         ".eyJzdWIiOiI1MDEzZDMwOS1jOTAyLTQzYzQtYWQ3MC05MzBjYzY1OWU0NzEiLCJ0eXBl"
         "IjoiQVBJX0tFWSIsIndvcmtzcGFjZUlkIjoiNTAxM2QzMDktYzkwMi00M2M0LWFkNzAtOT"
         "MwY2M2NTllNDcxIiwiaWF0IjoxNzc0NDAzMzAyLCJleHAiOjQ5MjgwMDMzMDEsImp0aSI6"
         "IjBkN2E1YTViLTFmYTUtNGI2Ny1iMzEwLWJkYWRiMzkyYTNmNSJ9"
         ".DPiIwzGz1lmReVKZcZYqGjb8iJHm38742uFIaYDGf7o")

TRAMITE_OBJ_ID = "1c87eb5b-cd45-4c88-ac74-2456bdd9ad85"

FIELDS = {
    "folioInterno":          "6a7f2cae-d65a-45ed-bef3-80b93b1879ab",
    "agenteTitular":         "d9df206e-7e9f-4633-8423-95c7af5e24ef",
    "tipoTramite":           "ab9353f7-d2b3-4f39-ad58-7c44e3815751",
    "especialistaAsignado":  "9a79e477-5ff5-491f-b751-8dab1993d967",
    "estadoTramite":         "98a522f0-65b7-4c6a-a2e5-3e799ffe22ea",
    "fechaLimiteSla":        "13d6cae8-3a21-4f26-8d19-4463ac05b801",
    "ramo":                  "7196d098-0f53-4e85-a84d-e2619322329b",
    "fueraDeSla":            "9f94402c-c0cd-4a94-9ea4-168606464914",
    "resultadoGnp":          "ee0b62c0-1788-4cbc-a403-fd8307b60afb",
    "razonRechazo":          "8b4ed78b-d865-46ee-97fd-9b807d104659",  # RELATION MANY_TO_ONE
    # ocultos
    "fechaEntrada":          "2f6da908-bd37-4dad-a8e4-d288c3368b8f",
    "nombreAsegurado":       "17a83965-385e-4792-8ff8-e8e2d39202a5",
    "numPolizaGnp":          "148311c4-ab52-4855-a4f6-1b6c56aa6dc9",
    "notasAnalista":         "3f5a83e4-9b8c-4c3d-acdc-4c3b24162768",
    "enviadoPor":            "c3879d08-5d43-4e60-9ad2-6649a820231c",
}

# ---- Vista 1: Todos los ramos -----------------------------------------------
# Columnas: Ramo al frente (es el campo de agrupacion), luego el resto
COLS_TODOS = [
    # visible
    {"fieldMetadataId": FIELDS["ramo"],                 "isVisible": True,  "position": 0, "size": 120},
    {"fieldMetadataId": FIELDS["folioInterno"],          "isVisible": True,  "position": 1, "size": 140},
    {"fieldMetadataId": FIELDS["agenteTitular"],         "isVisible": True,  "position": 2, "size": 190},
    {"fieldMetadataId": FIELDS["tipoTramite"],           "isVisible": True,  "position": 3, "size": 150},
    {"fieldMetadataId": FIELDS["especialistaAsignado"],  "isVisible": True,  "position": 4, "size": 180},
    {"fieldMetadataId": FIELDS["estadoTramite"],         "isVisible": True,  "position": 5, "size": 170},
    {"fieldMetadataId": FIELDS["fechaLimiteSla"],        "isVisible": True,  "position": 6, "size": 150},
    # ocultas
    {"fieldMetadataId": FIELDS["fueraDeSla"],            "isVisible": False, "position": 7,  "size": 110},
    {"fieldMetadataId": FIELDS["resultadoGnp"],          "isVisible": False, "position": 8,  "size": 130},
    {"fieldMetadataId": FIELDS["razonRechazo"],          "isVisible": False, "position": 9,  "size": 180},
    {"fieldMetadataId": FIELDS["fechaEntrada"],          "isVisible": False, "position": 10, "size": 140},
    {"fieldMetadataId": FIELDS["nombreAsegurado"],       "isVisible": False, "position": 11, "size": 180},
    {"fieldMetadataId": FIELDS["numPolizaGnp"],          "isVisible": False, "position": 12, "size": 150},
    {"fieldMetadataId": FIELDS["notasAnalista"],         "isVisible": False, "position": 13, "size": 180},
    {"fieldMetadataId": FIELDS["enviadoPor"],            "isVisible": False, "position": 14, "size": 160},
]

# ---- Vista 2: SLA global -----------------------------------------------------
# Columnas: indicadores de alerta al frente, luego ramo (agrupacion), luego detalle
COLS_SLA = [
    # visible
    {"fieldMetadataId": FIELDS["fueraDeSla"],            "isVisible": True,  "position": 0, "size": 110},
    {"fieldMetadataId": FIELDS["fechaLimiteSla"],        "isVisible": True,  "position": 1, "size": 150},
    {"fieldMetadataId": FIELDS["ramo"],                  "isVisible": True,  "position": 2, "size": 120},
    {"fieldMetadataId": FIELDS["folioInterno"],          "isVisible": True,  "position": 3, "size": 140},
    {"fieldMetadataId": FIELDS["agenteTitular"],         "isVisible": True,  "position": 4, "size": 190},
    {"fieldMetadataId": FIELDS["especialistaAsignado"],  "isVisible": True,  "position": 5, "size": 180},
    {"fieldMetadataId": FIELDS["estadoTramite"],         "isVisible": True,  "position": 6, "size": 170},
    # ocultas
    {"fieldMetadataId": FIELDS["tipoTramite"],           "isVisible": False, "position": 7,  "size": 150},
    {"fieldMetadataId": FIELDS["resultadoGnp"],          "isVisible": False, "position": 8,  "size": 130},
    {"fieldMetadataId": FIELDS["razonRechazo"],          "isVisible": False, "position": 9,  "size": 180},
    {"fieldMetadataId": FIELDS["fechaEntrada"],          "isVisible": False, "position": 10, "size": 140},
    {"fieldMetadataId": FIELDS["nombreAsegurado"],       "isVisible": False, "position": 11, "size": 180},
    {"fieldMetadataId": FIELDS["numPolizaGnp"],          "isVisible": False, "position": 12, "size": 150},
    {"fieldMetadataId": FIELDS["notasAnalista"],         "isVisible": False, "position": 13, "size": 180},
    {"fieldMetadataId": FIELDS["enviadoPor"],            "isVisible": False, "position": 14, "size": 160},
]

# ---- Vista 3: Rechazos GNP ---------------------------------------------------
# Columnas: resultado y razon de rechazo al frente (campo de agrupacion visible)
COLS_RECHAZOS = [
    # visible
    {"fieldMetadataId": FIELDS["resultadoGnp"],          "isVisible": True,  "position": 0, "size": 140},
    {"fieldMetadataId": FIELDS["razonRechazo"],          "isVisible": True,  "position": 1, "size": 200},
    {"fieldMetadataId": FIELDS["folioInterno"],          "isVisible": True,  "position": 2, "size": 140},
    {"fieldMetadataId": FIELDS["agenteTitular"],         "isVisible": True,  "position": 3, "size": 190},
    {"fieldMetadataId": FIELDS["tipoTramite"],           "isVisible": True,  "position": 4, "size": 150},
    {"fieldMetadataId": FIELDS["ramo"],                  "isVisible": True,  "position": 5, "size": 120},
    {"fieldMetadataId": FIELDS["estadoTramite"],         "isVisible": True,  "position": 6, "size": 170},
    # ocultas
    {"fieldMetadataId": FIELDS["especialistaAsignado"],  "isVisible": False, "position": 7,  "size": 180},
    {"fieldMetadataId": FIELDS["fechaLimiteSla"],        "isVisible": False, "position": 8,  "size": 150},
    {"fieldMetadataId": FIELDS["fueraDeSla"],            "isVisible": False, "position": 9,  "size": 110},
    {"fieldMetadataId": FIELDS["fechaEntrada"],          "isVisible": False, "position": 10, "size": 140},
    {"fieldMetadataId": FIELDS["nombreAsegurado"],       "isVisible": False, "position": 11, "size": 180},
    {"fieldMetadataId": FIELDS["numPolizaGnp"],          "isVisible": False, "position": 12, "size": 150},
    {"fieldMetadataId": FIELDS["notasAnalista"],         "isVisible": False, "position": 13, "size": 180},
    {"fieldMetadataId": FIELDS["enviadoPor"],            "isVisible": False, "position": 14, "size": 160},
]

VIEWS_CONFIG = [
    {
        "name":                       "Todos los ramos",
        "icon":                       "IconLayoutGrid",
        "position":                   13,
        "mainGroupByFieldMetadataId": FIELDS["ramo"],
        "cols":                       COLS_TODOS,
        "filters":                    [],
        "sort":                       None,
    },
    {
        "name":                       "SLA global",
        "icon":                       "IconAlertTriangle",
        "position":                   14,
        "mainGroupByFieldMetadataId": FIELDS["ramo"],
        "cols":                       COLS_SLA,
        "filters": [
            {
                "fieldMetadataId": FIELDS["fueraDeSla"],
                "operand":         "IS",
                "value":           "true",    # BOOLEAN: string "true"
            },
        ],
        "sort": {
            "fieldMetadataId": FIELDS["fechaLimiteSla"],
            "direction":       "ASC",
        },
    },
    {
        "name":                       "Rechazos GNP",
        "icon":                       "IconXboxX",
        "position":                   15,
        "mainGroupByFieldMetadataId": FIELDS["razonRechazo"],
        "cols":                       COLS_RECHAZOS,
        "filters": [
            {
                "fieldMetadataId": FIELDS["resultadoGnp"],
                "operand":         "IS",
                "value":           json.dumps(["RECHAZADO"]),   # SELECT: JSON array
            },
        ],
        "sort": None,
    },
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

# Mutations
CREATE_VIEW = """
mutation CreateView($input: CreateViewInput!) {
  createCoreView(input: $input) { id name type position mainGroupByFieldMetadataId }
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

# ---- Main --------------------------------------------------------------------
print("\n" + "="*65)
print("  SETUP VISTAS DIRECTORA (3 vistas globales) - Tramite")
print("="*65)

# Existing views
r = gql(f'{{ getCoreViews(objectMetadataId: "{TRAMITE_OBJ_ID}") {{ id name type position }} }}')
existing = {v["name"]: v for v in r["data"]["getCoreViews"]}
print(f"\nVistas existentes: {len(existing)}")
for name, v in sorted(existing.items(), key=lambda x: x[1]["position"]):
    print(f"  [{v['position']:2d}] {name}")

created_views = []

for cfg in VIEWS_CONFIG:
    view_name = cfg["name"]
    print(f"\n{'='*65}")
    print(f"  {view_name}")
    print(f"{'='*65}")

    if view_name in existing:
        vid = existing[view_name]["id"]
        log("-", f"Ya existe (id={vid[:8]}), saltando")
        created_views.append({"name": view_name, "id": vid})
        continue

    # 1. Crear vista
    r = gql(CREATE_VIEW, {"input": {
        "name":                       view_name,
        "objectMetadataId":           TRAMITE_OBJ_ID,
        "type":                       "TABLE",
        "icon":                       cfg["icon"],
        "visibility":                 "WORKSPACE",
        "position":                   cfg["position"],
        "isCompact":                  False,
        "mainGroupByFieldMetadataId": cfg["mainGroupByFieldMetadataId"],
    }})
    if "errors" in r:
        log("!", f"Crear vista: {r['errors'][0]['message'][:80]}")
        continue

    VIEW_ID = r["data"]["createCoreView"]["id"]
    group_id = r["data"]["createCoreView"].get("mainGroupByFieldMetadataId", "")[:8]
    log("+", f"Vista creada id={VIEW_ID[:8]}  groupBy={group_id}")
    created_views.append({"name": view_name, "id": VIEW_ID})

    # 2. Columnas
    all_cols = [{**c, "viewId": VIEW_ID} for c in cfg["cols"]]
    r = gql(CREATE_FIELDS, {"inputs": all_cols})
    if "errors" in r:
        log("!", f"Columnas: {r['errors'][0]['message'][:80]}")
    else:
        created = r["data"]["createManyCoreViewFields"]
        vis = sum(1 for c in created if c["isVisible"])
        log("+", f"{len(created)} campos ({vis} visibles)")

    # 3. Filtros
    for flt in cfg["filters"]:
        r = gql(CREATE_FILTER, {"input": {**flt, "viewId": VIEW_ID}})
        if "errors" in r:
            log("!", f"Filtro {flt['fieldMetadataId'][:8]}: {r['errors'][0]['message'][:80]}")
        else:
            f = r["data"]["createCoreViewFilter"]
            log("+", f"Filtro: {flt['fieldMetadataId'][:8]} {flt['operand']} {flt['value'][:30]}  id={f['id'][:8]}")

    # 4. Orden (si aplica)
    if cfg["sort"]:
        r = gql(CREATE_SORT, {"input": {**cfg["sort"], "viewId": VIEW_ID}})
        if "errors" in r:
            log("!", f"Sort: {r['errors'][0]['message'][:80]}")
        else:
            s = r["data"]["createCoreViewSort"]
            log("+", f"Orden: {cfg['sort']['fieldMetadataId'][:8]} {cfg['sort']['direction']}  id={s['id'][:8]}")

# ---- Verificacion final ------------------------------------------------------
print(f"\n{'='*65}")
print("  VERIFICACION FINAL")
print(f"{'='*65}")

r = gql(f'{{ getCoreViews(objectMetadataId: "{TRAMITE_OBJ_ID}") {{ id name type position mainGroupByFieldMetadataId }} }}')
all_views = sorted(r["data"]["getCoreViews"], key=lambda x: x["position"])
print(f"\n  Total vistas en Tramite: {len(all_views)}")

field_names = {v: k for k, v in FIELDS.items()}
for v in all_views:
    group = field_names.get(v.get("mainGroupByFieldMetadataId", ""), "-")
    print(f"  [{v['position']:2d}] {v['name']:35s}  grupo={group}")

print(f"\n  Detalle vistas directora:")
for cv in created_views:
    r2 = gql(f'{{ getCoreViewFilters(viewId: "{cv["id"]}") {{ fieldMetadataId operand value }} getCoreViewSorts(viewId: "{cv["id"]}") {{ fieldMetadataId direction }} }}')
    filters = r2["data"]["getCoreViewFilters"]
    sorts   = r2["data"]["getCoreViewSorts"]
    flt_desc = " AND ".join(
        f"{field_names.get(f['fieldMetadataId'], f['fieldMetadataId'][:8])} {f['operand']} {f['value'][:20]}"
        for f in filters
    ) or "sin filtro"
    srt_desc = ", ".join(f"{field_names.get(s['fieldMetadataId'], '?')} {s['direction']}" for s in sorts) or "-"
    print(f"\n    {cv['name']}")
    print(f"      filtros: {flt_desc}")
    print(f"      orden:   {srt_desc}")

print(f"\n{'='*65}")
print("  RESUMEN")
print(f"{'='*65}")
print(f"  [+] Exitosos: {ok}")
print(f"  [!] Fallidos: {fail}")
print()
print("  COMPORTAMIENTO PARA LA DIRECTORA:")
print("  Todos los ramos  - Vision completa agrupada por ramo, sin filtros")
print("  SLA global       - Solo tramites con SLA vencido, agrupados por ramo")
print("                     ordenados por fecha SLA ASC (los mas urgentes primero)")
print("  Rechazos GNP     - Solo tramites rechazados, agrupados por razon de rechazo")
print("                     momento wow: ver cual error es el mas comun de agentes")
print(f"{'='*65}")
