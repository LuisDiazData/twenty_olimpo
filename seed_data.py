#!/usr/bin/env python3
"""
Seed data de prueba para verificar el modelo completo de la promotoria GNP.
Crea registros en todos los objetos y verifica relaciones.
"""
import json, urllib.request, urllib.error, sys
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

BASE         = os.getenv("TWENTY_API_URL", "http://localhost:3000") + "/rest"
TOKEN        = "Bearer " + os.getenv("TWENTY_API_KEY", "")
WS_MEMBER_ID = os.getenv("TWENTY_WS_MEMBER_ID", "96fc35ea-4fa8-4388-956a-22ef62833c21")

ok = 0; fail = 0

def req(method, path, body=None):
    url  = f"{BASE}/{path}"
    data = json.dumps(body).encode() if body else None
    r    = urllib.request.Request(url, data=data,
             headers={"Authorization": TOKEN, "Content-Type": "application/json"},
             method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return json.loads(resp.read()), None
    except urllib.error.HTTPError as e:
        return None, json.loads(e.read())

def post(path, body, label):
    global ok, fail
    data, err = req("POST", path, body)
    if err:
        print(f"  [!] {label}: {str(err)[:120]}")
        fail += 1
        return None
    # Twenty REST returns { "data": { "<objectName>": {...} } } for single POST
    # or simply the object directly. Let's handle both.
    if isinstance(data, dict):
        # Try { "data": { ... } } wrapper first
        inner = data.get("data", data)
        if isinstance(inner, dict):
            # Might be { "createOneXxx": { "id": ... } } or just { "id": ... }
            for v in inner.values():
                if isinstance(v, dict) and "id" in v:
                    print(f"  [+] {label} id={v['id']}")
                    ok += 1
                    return v["id"]
            if "id" in inner:
                print(f"  [+] {label} id={inner['id']}")
                ok += 1
                return inner["id"]
    print(f"  [?] {label}: unexpected response {str(data)[:80]}")
    fail += 1
    return None

def get(path):
    data, err = req("GET", path)
    if err:
        return None
    return data

# ─────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("  SEED DATA - PROMOTORIA GNP")
print("="*60)

# ─────────────────────────────────────────────────────────────
print("\n[1] Agentes (Company)...")

a1 = post("companies", {
    "name": "Juan Ramirez Agente",
    "cua": "GNP-001234",
    "tipo": "INDIVIDUAL",
    "tipoAgente": "INDIVIDUAL",
    "rfc": "RAJJ800101ABC",
    "estatus": "ACTIVO",
    "estatusAgente": "ACTIVO",
    "fechaIncorporacion": "2018-06-01",
    "promotoria": "Promotoria CDMX Norte",
    "notasInternas": "Agente senior especializado en Vida y GMM",
    "ramosPrincipal": ["VIDA", "GMM"],
    "emailPrincipal": {"primaryEmail": "juan.ramirez@agente.com", "additionalEmails": []},
    "telefonoPrincipal": {
        "primaryPhoneNumber": "5512345678",
        "primaryPhoneCountryCode": "MX",
        "primaryPhoneCallingCode": "+52",
        "additionalPhones": []
    }
}, "Agente 1 - Juan Ramirez")

a2 = post("companies", {
    "name": "Lopez & Asociados Despacho",
    "cua": "GNP-005678",
    "tipo": "DESPACHO",
    "tipoAgente": "DESPACHO_FORMAL",
    "rfc": "LAD900215XYZ",
    "estatus": "ACTIVO",
    "estatusAgente": "ACTIVO",
    "fechaIncorporacion": "2021-01-15",
    "promotoria": "Promotoria Sur CDMX",
    "notasInternas": "Despacho con 3 asistentes, fuerte en Autos y PyME",
    "ramosPrincipal": ["AUTOS", "PYME"],
    "emailPrincipal": {"primaryEmail": "contacto@lopezasociados.com", "additionalEmails": []},
    "telefonoPrincipal": {
        "primaryPhoneNumber": "5598765432",
        "primaryPhoneCountryCode": "MX",
        "primaryPhoneCallingCode": "+52",
        "additionalPhones": []
    }
}, "Agente 2 - Lopez & Asociados")

# ─────────────────────────────────────────────────────────────
print("\n[2] Contactos (Person)...")

c1 = post("people", {
    "name": {"firstName": "Maria", "lastName": "Ramirez Torres"},
    "emails": {"primaryEmail": "maria.ramirez@gmail.com", "additionalEmails": []},
    "phones": {
        "primaryPhoneNumber": "5511223344",
        "primaryPhoneCountryCode": "MX",
        "primaryPhoneCallingCode": "+52",
        "additionalPhones": []
    },
    "email2": "maria.alt@hotmail.com",
    "whatsapp": "+525511223344",
    "rolContacto": "TITULAR",
    "contactoActivo": True,
    "companyId": a1
}, "Contacto 1 - Maria Ramirez (titular de Agente 1)")

c2 = post("people", {
    "name": {"firstName": "Carlos", "lastName": "Lopez Mendez"},
    "emails": {"primaryEmail": "carlos.lopez@lopezasociados.com", "additionalEmails": []},
    "phones": {
        "primaryPhoneNumber": "5544556677",
        "primaryPhoneCountryCode": "MX",
        "primaryPhoneCallingCode": "+52",
        "additionalPhones": []
    },
    "whatsapp": "+525544556677",
    "rolContacto": "ASISTENTE",
    "contactoActivo": True,
    "companyId": a2
}, "Contacto 2 - Carlos Lopez (asistente de Agente 2)")

# ─────────────────────────────────────────────────────────────
print("\n[3] Asignaciones...")

asig1 = post("asignaciones", {
    "name": "Ramirez - Vida",
    "ramo": "VIDA",
    "asignacionActiva": True,
    "fechaDesde": "2024-01-01",
    "agenteId": a1,
    "especialistaId": WS_MEMBER_ID
}, "Asignacion 1 - Ramirez / Vida")

asig2 = post("asignaciones", {
    "name": "Lopez - Autos",
    "ramo": "AUTOS",
    "asignacionActiva": True,
    "fechaDesde": "2024-03-01",
    "agenteId": a2,
    "especialistaId": WS_MEMBER_ID
}, "Asignacion 2 - Lopez / Autos")

# ─────────────────────────────────────────────────────────────
print("\n[4] Tramites...")

t1 = post("tramites", {
    "name": "TRM-2024-001",
    "folioInterno": "TRM-2024-001",
    "tipoTramite": "NUEVA_POLIZA",
    "ramo": "VIDA",
    "estadoTramite": "EN_REVISION",
    "resultadoGnp": "PENDIENTE",
    "fechaEntrada": "2024-11-01",
    "fechaLimiteSla": "2024-11-10",
    "fueraDeSla": False,
    "nombreAsegurado": "Pedro Sanchez Gomez",
    "numPolizaGnp": "",
    "notasAnalista": "Documentacion recibida por WhatsApp. Falta acta de nacimiento.",
    "agenteTitularId": a1,
    "enviadoPorId": c1,
    "especialistaAsignadoId": WS_MEMBER_ID
}, "Tramite 1 - TRM-2024-001 (Vida, En revision)")

t2 = post("tramites", {
    "name": "TRM-2024-002",
    "folioInterno": "TRM-2024-002",
    "tipoTramite": "SINIESTRO",
    "ramo": "AUTOS",
    "estadoTramite": "ENVIADO_A_GNP",
    "resultadoGnp": "PENDIENTE",
    "fechaEntrada": "2024-10-15",
    "fechaLimiteSla": "2024-10-25",
    "fueraDeSla": False,
    "nombreAsegurado": "Ana Lucia Vega",
    "numPolizaGnp": "POL-AUTOS-78945",
    "notasAnalista": "Siniestro por colision. Documentacion completa. Enviado a GNP el 20-Oct.",
    "agenteTitularId": a2,
    "enviadoPorId": c2,
    "especialistaAsignadoId": WS_MEMBER_ID
}, "Tramite 2 - TRM-2024-002 (Autos, Enviado GNP)")

t3 = post("tramites", {
    "name": "TRM-2024-003",
    "folioInterno": "TRM-2024-003",
    "tipoTramite": "ENDOSO",
    "ramo": "GMM",
    "estadoTramite": "RECHAZADO_GNP",
    "resultadoGnp": "RECHAZADO",
    "fechaEntrada": "2024-09-01",
    "fechaLimiteSla": "2024-09-15",
    "fueraDeSla": True,
    "nombreAsegurado": "Roberto Herrera Nuez",
    "numPolizaGnp": "POL-GMM-12345",
    "notasAnalista": "Rechazado por GNP. Firma del contratante no coincide.",
    "agenteTitularId": a1,
    "enviadoPorId": c1,
    "especialistaAsignadoId": WS_MEMBER_ID
}, "Tramite 3 - TRM-2024-003 (GMM, Rechazado)")

# ─────────────────────────────────────────────────────────────
print("\n[5] Documentos...")

d1 = post("documentos", {
    "name": "INE-Pedro-Sanchez",
    "tipoDocumento": "INE",
    "estadoDoc": "RECIBIDO",
    "notasDoc": "INE vigente, copia clara",
    "fechaRecepcion": "2024-11-01",
    "tramiteId": t1
}, "Doc 1 - INE (TRM-001)")

d2 = post("documentos", {
    "name": "Acta-Pedro-Sanchez",
    "tipoDocumento": "ACTA_NACIMIENTO",
    "estadoDoc": "FALTA",
    "notasDoc": "Pendiente de envio por parte del agente",
    "fechaRecepcion": None,
    "tramiteId": t1
}, "Doc 2 - Acta nacimiento FALTA (TRM-001)")

d3 = post("documentos", {
    "name": "Solicitud-Ana-Vega",
    "tipoDocumento": "SOLICITUD_FIRMADA",
    "estadoDoc": "RECIBIDO",
    "notasDoc": "Solicitud firmada y escaneada correctamente",
    "fechaRecepcion": "2024-10-16",
    "tramiteId": t2
}, "Doc 3 - Solicitud firmada (TRM-002)")

d4 = post("documentos", {
    "name": "Poliza-Roberto-Herrera",
    "tipoDocumento": "CARATULA_POLIZA",
    "estadoDoc": "RECHAZADO",
    "notasDoc": "Firma del contratante no coincide con la poliza original",
    "fechaRecepcion": "2024-09-02",
    "tramiteId": t3
}, "Doc 4 - Caratula poliza RECHAZADA (TRM-003)")

# ─────────────────────────────────────────────────────────────
print("\n[6] Razones de Rechazo...")

r1 = post("razonesRechazo", {
    "name": "Firma no coincide - GMM",
    "categoria": "DATOS_INCORRECTOS",
    "descripcion": "La firma del contratante en el endoso no coincide con la poliza original. GNP solicita nueva firma notariada.",
    "frecuencia": 3,
    "tramiteId": t3
}, "Razon Rechazo 1 - Firma no coincide (TRM-003)")

r2 = post("razonesRechazo", {
    "name": "Documentacion incompleta - Vida",
    "categoria": "DOCUMENTACION_INCOMPLETA",
    "descripcion": "Falta acta de nacimiento del asegurado. Es requisito obligatorio para polizas de Vida nueva emision.",
    "frecuencia": 8,
    "tramiteId": t1
}, "Razon Rechazo 2 - Doc incompleta (TRM-001)")

# ─────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("  VERIFICACION DE RELACIONES")
print("="*60)

# Verify Tramite 1 with relations
print("\n[V1] Tramite TRM-2024-001 con relaciones:")
if t1:
    data = get(f"tramites/{t1}")
    if data:
        tramite_data = data.get("data", {})
        # Find tramite in response
        for k, v in tramite_data.items():
            if isinstance(v, dict) and "id" in v:
                tramite_data = v
                break
        if isinstance(tramite_data, dict) and "folioInterno" in tramite_data:
            print(f"  folio:       {tramite_data.get('folioInterno')}")
            print(f"  tipo:        {tramite_data.get('tipoTramite')}")
            print(f"  ramo:        {tramite_data.get('ramo')}")
            print(f"  estado:      {tramite_data.get('estadoTramite')}")
            print(f"  agenteTitularId: {tramite_data.get('agenteTitularId')}")
            print(f"  enviadoPorId:    {tramite_data.get('enviadoPorId')}")
            print(f"  especialistaAsignadoId: {tramite_data.get('especialistaAsignadoId')}")
        else:
            print(f"  raw: {str(tramite_data)[:200]}")

# Verify documents linked to tramite 1
print(f"\n[V2] Documentos de TRM-2024-001:")
if t1:
    data = get(f"documentos?filter=tramiteId[eq]:{t1}")
    if data:
        docs = data.get("data", {}).get("documentos", [])
        for doc in docs:
            print(f"  [{doc.get('estadoDoc')}] {doc.get('tipoDocumento')} - {doc.get('notasDoc','')[:50]}")

# Verify Asignaciones
print(f"\n[V3] Asignaciones del Agente 1:")
if a1:
    data = get(f"asignaciones?filter=agenteId[eq]:{a1}")
    if data:
        asigs = data.get("data", {}).get("asignaciones", [])
        for a in asigs:
            print(f"  ramo={a.get('ramo')} activa={a.get('asignacionActiva')} desde={a.get('fechaDesde')}")

# ─────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("  RESUMEN FINAL")
print("="*60)
counts = {}
for endpoint, key in [("companies","companies"), ("people","people"),
                       ("asignaciones","asignaciones"), ("tramites","tramites"),
                       ("documentos","documentos"), ("razonesRechazo","razonesRechazo")]:
    data = get(endpoint)
    if data:
        counts[key] = data.get("totalCount", "?")

for k, v in counts.items():
    print(f"  {k:30s} {v} registros")

print(f"\n  [+] Creados: {ok}   [!] Fallidos: {fail}")
print("="*60)
