#!/usr/bin/env python3
"""
seed_catalogo_tipos.py
Pobla catalogoTipoDocumento (13 tipos) y motivoRechazo (6 motivos) en Twenty CRM.

Idempotente: verifica por 'clave' antes de insertar, no duplica.
Uso:
  python3 scripts/seed_catalogo_tipos.py [--force]

--force: actualiza registros existentes en lugar de saltarlos.
"""
import argparse
import os
import sys
import httpx
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / "packages/twenty-docker/.env")

TWENTY_API_URL = os.getenv("TWENTY_API_URL", "http://localhost:3000")
TWENTY_API_KEY = os.getenv("TWENTY_API_KEY", "")

# ── Datos ──────────────────────────────────────────────────────────────────────

TIPOS_DOCUMENTO = [
    {
        "clave": "INE",
        "nombre": "INE / IFE",
        "ramo": None,
        "tipoTramite": None,
        "esObligatorio": True,
        "activo": True,
        "descripcion": "Identificación oficial emitida por el INE/IFE",
        "instruccionesValidacion": "Vigente, ambas caras legibles, sin tachaduras ni alteraciones",
    },
    {
        "clave": "POL_GNP",
        "nombre": "Póliza GNP",
        "ramo": None,
        "tipoTramite": "Renovacion",
        "esObligatorio": True,
        "activo": True,
        "descripcion": "Póliza de seguro emitida por GNP",
        "instruccionesValidacion": "Número de póliza visible, período de vigencia legible",
    },
    {
        "clave": "SOL_GNP",
        "nombre": "Solicitud de seguro GNP",
        "ramo": None,
        "tipoTramite": "Emision",
        "esObligatorio": True,
        "activo": True,
        "descripcion": "Formato de solicitud de nueva póliza GNP",
        "instruccionesValidacion": "Firmada por el solicitante, todos los campos obligatorios llenos",
    },
    {
        "clave": "COMP_DOM",
        "nombre": "Comprobante de domicilio",
        "ramo": None,
        "tipoTramite": None,
        "esObligatorio": True,
        "activo": True,
        "descripcion": "Comprobante de domicilio reciente",
        "instruccionesValidacion": "No mayor a 3 meses, nombre y dirección legibles",
    },
    {
        "clave": "COMP_PAGO",
        "nombre": "Comprobante de pago",
        "ramo": None,
        "tipoTramite": None,
        "esObligatorio": False,
        "activo": True,
        "descripcion": "Comprobante de pago de prima de seguro",
        "instruccionesValidacion": "Monto, fecha y número de referencia visibles",
    },
    {
        "clave": "CFDI",
        "nombre": "CFDI / Factura",
        "ramo": None,
        "tipoTramite": None,
        "esObligatorio": False,
        "activo": True,
        "descripcion": "Comprobante Fiscal Digital por Internet",
        "instruccionesValidacion": "UUID y sello del SAT presentes, no cancelado",
    },
    {
        "clave": "ACTA_NAC",
        "nombre": "Acta de nacimiento",
        "ramo": "Vida",
        "tipoTramite": None,
        "esObligatorio": False,
        "activo": True,
        "descripcion": "Acta de nacimiento oficial del asegurado",
        "instruccionesValidacion": "Sellada por el Registro Civil, legible",
    },
    {
        "clave": "CARTA_INS",
        "nombre": "Carta de instrucción",
        "ramo": None,
        "tipoTramite": "Endoso",
        "esObligatorio": True,
        "activo": True,
        "descripcion": "Carta de instrucción firmada por el asegurado o agente",
        "instruccionesValidacion": "Firmada, con fecha, indicando tipo de endoso solicitado",
    },
    {
        "clave": "PASAPORTE",
        "nombre": "Pasaporte",
        "ramo": None,
        "tipoTramite": None,
        "esObligatorio": False,
        "activo": True,
        "descripcion": "Pasaporte mexicano o extranjero vigente",
        "instruccionesValidacion": "Vigente, página de datos personales legible",
    },
    {
        "clave": "FMT_GNP",
        "nombre": "Formato GNP",
        "ramo": None,
        "tipoTramite": None,
        "esObligatorio": False,
        "activo": True,
        "descripcion": "Formato oficial interno de GNP",
        "instruccionesValidacion": "Completamente llenado y firmado por todas las partes",
    },
    {
        "clave": "CARNET",
        "nombre": "Carnet de salud",
        "ramo": "GMM",
        "tipoTramite": None,
        "esObligatorio": False,
        "activo": True,
        "descripcion": "Historial médico o carnet de salud del asegurado",
        "instruccionesValidacion": "Firmado por médico, fechas y datos legibles",
    },
    {
        "clave": "EDO_CUENTA",
        "nombre": "Estado de cuenta",
        "ramo": None,
        "tipoTramite": None,
        "esObligatorio": False,
        "activo": True,
        "descripcion": "Estado de cuenta bancario para domiciliación",
        "instruccionesValidacion": "No mayor a 3 meses, CLABE interbancaria visible",
    },
    {
        "clave": "OTRO",
        "nombre": "Otro",
        "ramo": None,
        "tipoTramite": None,
        "esObligatorio": False,
        "activo": True,
        "descripcion": "Documento no categorizado por el sistema",
        "instruccionesValidacion": "Revisar manualmente y reclasificar si es posible",
    },
]

MOTIVOS_RECHAZO = [
    {
        "clave": "ILEGIBLE",
        "descripcion": "El documento no puede ser leído por problemas de calidad de imagen",
        "categoria": "Documento",
        "ramo": None,
        "tipoTramite": None,
        "accionRecomendada": "Solicitar al remitente reenviar el documento con mejor resolución (mínimo 300 DPI)",
        "tiempoEstimadoSubsanacionHoras": 24,
        "esRechazoGnp": False,
        "activo": True,
    },
    {
        "clave": "ENCRIPTADO",
        "descripcion": "El documento está protegido con contraseña y no se pudo desencriptar automáticamente",
        "categoria": "Documento",
        "ramo": None,
        "tipoTramite": None,
        "accionRecomendada": "Solicitar al remitente la contraseña del archivo o reenviar sin protección",
        "tiempoEstimadoSubsanacionHoras": 4,
        "esRechazoGnp": False,
        "activo": True,
    },
    {
        "clave": "OCR_ERROR",
        "descripcion": "Error técnico al intentar extraer texto del documento mediante OCR",
        "categoria": "Tecnico",
        "ramo": None,
        "tipoTramite": None,
        "accionRecomendada": "Revisar manualmente el documento original en la bandeja de documentos",
        "tiempoEstimadoSubsanacionHoras": 2,
        "esRechazoGnp": False,
        "activo": True,
    },
    {
        "clave": "INCOMPLETO",
        "descripcion": "El documento está incompleto, le faltan páginas o campos requeridos",
        "categoria": "Documento",
        "ramo": None,
        "tipoTramite": None,
        "accionRecomendada": "Solicitar el documento completo con todas las páginas requeridas",
        "tiempoEstimadoSubsanacionHoras": 48,
        "esRechazoGnp": True,
        "activo": True,
    },
    {
        "clave": "VENCIDO",
        "descripcion": "El documento presenta fecha de vencimiento expirada",
        "categoria": "Documento",
        "ramo": None,
        "tipoTramite": None,
        "accionRecomendada": "Solicitar documento vigente. Verificar fecha de vencimiento antes de reenviar",
        "tiempoEstimadoSubsanacionHoras": 72,
        "esRechazoGnp": True,
        "activo": True,
    },
    {
        "clave": "FORMATO_NO_SOPORTADO",
        "descripcion": "El tipo de archivo no es procesable por el sistema de IA",
        "categoria": "Tecnico",
        "ramo": None,
        "tipoTramite": None,
        "accionRecomendada": "Solicitar el documento en formato PDF, JPG o PNG",
        "tiempoEstimadoSubsanacionHoras": 4,
        "esRechazoGnp": False,
        "activo": True,
    },
]

# ── GraphQL helpers ────────────────────────────────────────────────────────────

def gql(query: str, variables: dict | None = None) -> dict:
    headers = {
        "Authorization": f"Bearer {TWENTY_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    resp = httpx.post(
        f"{TWENTY_API_URL}/graphql",
        json=payload,
        headers=headers,
        timeout=20.0,
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("errors"):
        raise ValueError(f"GraphQL errors: {body['errors']}")
    return body.get("data") or {}


def find_by_clave(object_plural: str, clave: str) -> str | None:
    """Busca un objeto por el campo 'clave'. Retorna su ID o None."""
    query = f"""
    query FindByClave($filter: {object_plural.rstrip('s').capitalize()}FilterInput) {{
      {object_plural}(filter: $filter, first: 1) {{
        edges {{ node {{ id clave }} }}
      }}
    }}
    """
    # Simplificado: búsqueda directa
    query = """
    query FindByClave($clave: String!) {
      """ + object_plural + """(filter: { clave: { eq: $clave } }, first: 1) {
        edges { node { id clave } }
      }
    }
    """
    try:
        data = gql(query, {"clave": clave})
        edges = data.get(object_plural, {}).get("edges", [])
        if edges:
            return edges[0]["node"]["id"]
    except Exception as e:
        print(f"  ⚠ find_by_clave {object_plural}/{clave}: {e}")
    return None


# ── Seed functions ─────────────────────────────────────────────────────────────

def seed_tipos_documento(force: bool = False) -> None:
    print("\n── Poblando catalogoTipoDocumento ──────────────────────────────")
    created = updated = skipped = 0

    for item in TIPOS_DOCUMENTO:
        clave = item["clave"]
        existing_id = find_by_clave("catalogoTipoDocumentos", clave)

        if existing_id and not force:
            print(f"  ↷ {clave} — ya existe (skip)")
            skipped += 1
            continue

        input_data: dict = {
            "name":                    item["nombre"],
            "clave":                   clave,
            "nombre":                  item["nombre"],
            "esObligatorio":           item["esObligatorio"],
            "activo":                  item["activo"],
        }
        if item.get("descripcion"):
            input_data["descripcion"] = item["descripcion"]
        if item.get("instruccionesValidacion"):
            input_data["instruccionesValidacion"] = item["instruccionesValidacion"]
        if item.get("ramo"):
            input_data["ramo"] = item["ramo"]
        if item.get("tipoTramite"):
            input_data["tipoTramite"] = item["tipoTramite"]

        try:
            if existing_id and force:
                gql(
                    """
                    mutation UpdateTipo($id: ID!, $data: CatalogoTipoDocumentoUpdateInput!) {
                      updateCatalogoTipoDocumento(id: $id, data: $data) { id clave }
                    }
                    """,
                    {"id": existing_id, "data": input_data},
                )
                print(f"  ✓ {clave} — actualizado")
                updated += 1
            else:
                gql(
                    """
                    mutation CreateTipo($data: CatalogoTipoDocumentoCreateInput!) {
                      createCatalogoTipoDocumento(data: $data) { id clave }
                    }
                    """,
                    {"data": input_data},
                )
                print(f"  + {clave} — creado")
                created += 1
        except Exception as e:
            print(f"  ✗ {clave} — error: {e}")

    print(f"\n  Tipos de documento: {created} creados, {updated} actualizados, {skipped} omitidos")


def seed_motivos_rechazo(force: bool = False) -> None:
    print("\n── Poblando motivoRechazo ──────────────────────────────────────")
    created = updated = skipped = 0

    for item in MOTIVOS_RECHAZO:
        clave = item["clave"]
        existing_id = find_by_clave("motivoRechazos", clave)

        if existing_id and not force:
            print(f"  ↷ {clave} — ya existe (skip)")
            skipped += 1
            continue

        input_data: dict = {
            "name":         item["descripcion"][:100],
            "clave":        clave,
            "descripcion":  item["descripcion"],
            "esRechazoGnp": item["esRechazoGnp"],
            "activo":       item["activo"],
        }
        if item.get("categoria"):
            input_data["categoria"] = item["categoria"]
        if item.get("accionRecomendada"):
            input_data["accionRecomendada"] = item["accionRecomendada"]
        if item.get("tiempoEstimadoSubsanacionHoras") is not None:
            input_data["tiempoEstimadoSubsanacionHoras"] = item["tiempoEstimadoSubsanacionHoras"]
        if item.get("ramo"):
            input_data["ramo"] = item["ramo"]
        if item.get("tipoTramite"):
            input_data["tipoTramite"] = item["tipoTramite"]

        try:
            if existing_id and force:
                gql(
                    """
                    mutation UpdateMotivo($id: ID!, $data: MotivoRechazoUpdateInput!) {
                      updateMotivoRechazo(id: $id, data: $data) { id clave }
                    }
                    """,
                    {"id": existing_id, "data": input_data},
                )
                print(f"  ✓ {clave} — actualizado")
                updated += 1
            else:
                gql(
                    """
                    mutation CreateMotivo($data: MotivoRechazoCreateInput!) {
                      createMotivoRechazo(data: $data) { id clave }
                    }
                    """,
                    {"data": input_data},
                )
                print(f"  + {clave} — creado")
                created += 1
        except Exception as e:
            print(f"  ✗ {clave} — error: {e}")

    print(f"\n  Motivos de rechazo: {created} creados, {updated} actualizados, {skipped} omitidos")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Seed de catálogos en Twenty CRM")
    parser.add_argument("--force", action="store_true", help="Actualizar registros existentes")
    args = parser.parse_args()

    if not TWENTY_API_KEY:
        print("ERROR: TWENTY_API_KEY no configurado. Verifica tu .env")
        sys.exit(1)

    print(f"Conectando a Twenty CRM en {TWENTY_API_URL}")
    if args.force:
        print("Modo --force: se actualizarán registros existentes")

    seed_tipos_documento(force=args.force)
    seed_motivos_rechazo(force=args.force)

    print("\n✓ Seed completado")


if __name__ == "__main__":
    main()
