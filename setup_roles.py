#!/usr/bin/env python3
"""
Configura los roles y permisos del modelo Promotoria GNP en Twenty CRM.

Roles a crear:
  Directora          -> Admin total (todo + settings)
  Gerente de Ramo    -> Operacional (todo excepto settings y destruir)
  Especialista       -> Operacional limitado (leer/editar los suyos, no destruir)

Luis Diaz (unico miembro actual) queda como Directora.
"""
import json, urllib.request, urllib.error
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

ENDPOINT       = os.getenv("TWENTY_API_URL", "http://localhost:3000") + "/metadata"
TOKEN          = "Bearer " + os.getenv("TWENTY_API_KEY", "")
WS_MEMBER_LUIS = os.getenv("TWENTY_WS_MEMBER_ID", "96fc35ea-4fa8-4388-956a-22ef62833c21")

# Object metadata IDs (from id_map + setup run)
OBJECTS = {
    "company":      "58697ca3-1a17-4298-b08b-22d53e180486",  # Agente
    "person":       "31d77925-61a1-4ddb-9ca9-c1f58a841d30",  # Contacto
    "tramite":      "1c87eb5b-cd45-4c88-ac74-2456bdd9ad85",
    "documento":    "de84e18f-e9fd-4421-8cd2-9a09301aec8e",
    "asignacion":   "28b8ef09-8842-43ae-a5f7-a3a002c6bb69",
    "razonRechazo": "3e6bb369-882b-436b-b925-8cb13ccdf612",
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
    print(f"  {icons.get(status, status)} {msg}")
    if status == "+": ok += 1
    elif status == "!": fail += 1

# ─── Paso 1: Obtener roles existentes ─────────────────────────────────────────
print("\n" + "="*60)
print("  SETUP ROLES Y PERMISOS - PROMOTORIA GNP")
print("="*60)

print("\n[PASO 1] Roles existentes en el workspace...")
r = gql("{ getRoles { id label isEditable workspaceMembers { id } } }")
existing_roles = {role["label"]: role for role in r["data"]["getRoles"]}
for label, role in existing_roles.items():
    members_count = len(role.get("workspaceMembers") or [])
    print(f"  [-] '{label}' id={role['id']} editable={role['isEditable']} miembros={members_count}")

# ─── Paso 2: Crear roles custom ───────────────────────────────────────────────
print("\n[PASO 2] Creando roles de la promotoria...")

CREATE_ROLE = """
mutation CreateRole($input: CreateRoleInput!) {
  createOneRole(createRoleInput: $input) {
    id label description canUpdateAllSettings
    canReadAllObjectRecords canUpdateAllObjectRecords
    canSoftDeleteAllObjectRecords canDestroyAllObjectRecords
  }
}"""

ROLES_TO_CREATE = [
    {
        "label":                      "Directora",
        "description":                "Directora General / Directora de Operaciones. Acceso total incluyendo configuracion del sistema.",
        "icon":                       "IconCrown",
        "canBeAssignedToUsers":       True,
        "canUpdateAllSettings":       True,
        "canAccessAllTools":          True,
        "canReadAllObjectRecords":    True,
        "canUpdateAllObjectRecords":  True,
        "canSoftDeleteAllObjectRecords": True,
        "canDestroyAllObjectRecords": True,
    },
    {
        "label":                      "Gerente de Ramo",
        "description":                "Gerente de Vida, GMM, PyMES o Autos. Acceso completo a tramites sin configuracion del sistema.",
        "icon":                       "IconUsers",
        "canBeAssignedToUsers":       True,
        "canUpdateAllSettings":       False,
        "canAccessAllTools":          False,
        "canReadAllObjectRecords":    True,
        "canUpdateAllObjectRecords":  True,
        "canSoftDeleteAllObjectRecords": True,
        "canDestroyAllObjectRecords": False,
    },
    {
        "label":                      "Especialista",
        "description":                "Analista operativo. Crea y edita tramites y documentos. No puede eliminar ni acceder a configuracion.",
        "icon":                       "IconUser",
        "canBeAssignedToUsers":       True,
        "canUpdateAllSettings":       False,
        "canAccessAllTools":          False,
        "canReadAllObjectRecords":    True,
        "canUpdateAllObjectRecords":  True,
        "canSoftDeleteAllObjectRecords": False,
        "canDestroyAllObjectRecords": False,
    },
]

created_roles = {}  # label -> id

for role_input in ROLES_TO_CREATE:
    label = role_input["label"]
    if label in existing_roles:
        log("-", f"Rol '{label}' ya existe, usando id existente")
        created_roles[label] = existing_roles[label]["id"]
        continue

    r = gql(CREATE_ROLE, {"input": role_input})
    if "errors" in r:
        log("!", f"Crear rol '{label}': {r['errors'][0]['message'][:80]}")
    else:
        role = r["data"]["createOneRole"]
        created_roles[label] = role["id"]
        log("+", f"Rol '{label}' creado id={role['id']}")

# ─── Paso 3: Permisos por objeto por rol ──────────────────────────────────────
print("\n[PASO 3] Configurando permisos por objeto...")

UPSERT_OBJ_PERMS = """
mutation UpsertObjectPermissions($input: UpsertObjectPermissionsInput!) {
  upsertObjectPermissions(upsertObjectPermissionsInput: $input) {
    canReadObjectRecords canUpdateObjectRecords
    canSoftDeleteObjectRecords canDestroyObjectRecords
  }
}"""

# Permisos por rol:
# - Directora: ya tiene canReadAll/UpdateAll desde el rol mismo — no necesita object-level
# - Gerente de Ramo: todos los objetos, sin destroy
# - Especialista: todos los objetos, sin softDelete ni destroy
perms_config = {
    "Gerente de Ramo": {
        obj_id: {
            "canReadObjectRecords":       True,
            "canUpdateObjectRecords":     True,
            "canSoftDeleteObjectRecords": True,
            "canDestroyObjectRecords":    False,
        }
        for obj_id in OBJECTS.values()
    },
    "Especialista": {
        obj_id: {
            "canReadObjectRecords":       True,
            "canUpdateObjectRecords":     True,
            "canSoftDeleteObjectRecords": False,
            "canDestroyObjectRecords":    False,
        }
        for obj_id in OBJECTS.values()
    },
}

for role_label, obj_perms in perms_config.items():
    role_id = created_roles.get(role_label)
    if not role_id:
        log("!", f"No se encontro id para rol '{role_label}', saltando permisos")
        continue

    permissions_list = [
        {"objectMetadataId": obj_id, **perms}
        for obj_id, perms in obj_perms.items()
    ]

    r = gql(UPSERT_OBJ_PERMS, {"input": {
        "roleId": role_id,
        "objectPermissions": permissions_list
    }})

    if "errors" in r:
        log("!", f"Permisos '{role_label}': {r['errors'][0]['message'][:80]}")
    else:
        configured = len(r["data"].get("upsertObjectPermissions") or [])
        log("+", f"Permisos '{role_label}': {configured} objetos configurados")

# ─── Paso 4: Asignar Luis Diaz a Directora ────────────────────────────────────
print("\n[PASO 4] Asignando rol 'Directora' a Luis Diaz...")

ASSIGN_ROLE = """
mutation AssignRole($memberId: UUID!, $roleId: UUID!) {
  updateWorkspaceMemberRole(workspaceMemberId: $memberId, roleId: $roleId) {
    id name { firstName lastName }
  }
}"""

directora_id = created_roles.get("Directora")
if directora_id:
    r = gql(ASSIGN_ROLE, {"memberId": WS_MEMBER_LUIS, "roleId": directora_id})
    if "errors" in r:
        # Might already be assigned
        if "already" in str(r["errors"]).lower():
            log("-", "Luis Diaz ya tiene el rol Directora")
        else:
            log("!", f"Asignar rol: {r['errors'][0]['message'][:80]}")
    else:
        member = r["data"]["updateWorkspaceMemberRole"]
        log("+", f"Luis Diaz asignado a 'Directora'")
else:
    log("!", "No se pudo obtener id del rol Directora")

# ─── Paso 5: Verificacion final ───────────────────────────────────────────────
print("\n[PASO 5] Verificacion final...")

r = gql("""{ getRoles {
  id label description isEditable
  canUpdateAllSettings canReadAllObjectRecords
  canUpdateAllObjectRecords canSoftDeleteAllObjectRecords canDestroyAllObjectRecords
  workspaceMembers { id name { firstName lastName } }
  objectPermissions { canReadObjectRecords canUpdateObjectRecords
    canSoftDeleteObjectRecords canDestroyObjectRecords }
} }""")

if "errors" in r:
    log("!", f"Verificacion: {r['errors'][0]['message'][:80]}")
else:
    roles = r["data"]["getRoles"]
    for role in roles:
        members = [f"{m['name']['firstName']} {m['name']['lastName']}"
                   for m in (role.get("workspaceMembers") or [])]
        obj_perms_count = len(role.get("objectPermissions") or [])
        print(f"\n  Rol: {role['label']}")
        print(f"    settings={role['canUpdateAllSettings']}  "
              f"readAll={role['canReadAllObjectRecords']}  "
              f"updateAll={role['canUpdateAllObjectRecords']}  "
              f"softDel={role['canSoftDeleteAllObjectRecords']}  "
              f"destroy={role['canDestroyAllObjectRecords']}")
        print(f"    object_permissions_configured={obj_perms_count}")
        print(f"    miembros: {members or ['ninguno']}")

print("\n" + "="*60)
print("  RESUMEN")
print("="*60)
print(f"  [+] Exitosos: {ok}")
print(f"  [!] Fallidos: {fail}")
print()
print("  ROLES DISPONIBLES:")
for label, rid in created_roles.items():
    print(f"    {label:25s}  id={rid}")
print()
print("  COMO ASIGNAR NUEVOS MIEMBROS:")
print("  1. Invitar usuario en Settings > Members")
print("  2. Usar updateWorkspaceMemberRole con el roleId correspondiente")
print("     o directamente desde la UI en Settings > Members > editar rol")
print("="*60)
