"""
twenty_sync.py — Sincronización con Twenty CRM para el pipeline de documentos.

Principio: Twenty es best-effort. Supabase es la fuente de verdad.
Si Twenty no está disponible, se loguea y el pipeline continúa sin bloqueo.

Circuit breaker: 3 fallos consecutivos → pausa 60 segundos.
Cache de catálogos: 5 minutos TTL para evitar round-trips repetidos.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Literal, Optional

import httpx

logger = logging.getLogger(__name__)

TWENTY_API_URL = os.getenv("TWENTY_API_URL", "http://localhost:3000")
TWENTY_API_KEY = os.getenv("TWENTY_API_KEY", "")
TWENTY_GQL_URL = f"{TWENTY_API_URL}/graphql"

# ── Circuit breaker ────────────────────────────────────────────────────────────

class _CircuitBreaker:
    _failures: int = 0
    _open_until: Optional[datetime] = None
    _THRESHOLD = 3
    _COOLDOWN_SECONDS = 60

    @classmethod
    def is_open(cls) -> bool:
        if cls._open_until and datetime.utcnow() < cls._open_until:
            return True
        if cls._open_until and datetime.utcnow() >= cls._open_until:
            # Cooldown expired — reset
            cls._failures = 0
            cls._open_until = None
        return False

    @classmethod
    def record_failure(cls) -> None:
        cls._failures += 1
        if cls._failures >= cls._THRESHOLD:
            cls._open_until = datetime.utcnow() + timedelta(seconds=cls._COOLDOWN_SECONDS)
            logger.warning(
                f"[twenty_sync] Circuit breaker OPEN — Twenty inaccesible. "
                f"Reintentos pausados hasta {cls._open_until.isoformat()}"
            )

    @classmethod
    def record_success(cls) -> None:
        if cls._failures > 0:
            logger.info("[twenty_sync] Circuit breaker cerrado — Twenty accesible nuevamente")
        cls._failures = 0
        cls._open_until = None


# ── Cache de catálogos (in-process, TTL 5 min) ────────────────────────────────

_cache_tipo_doc: dict[str, str] = {}   # clave_twenty → id en Twenty
_cache_tipo_doc_ttl: Optional[datetime] = None

_cache_motivo: dict[str, str] = {}    # clave_motivo → id en Twenty
_cache_motivo_ttl: Optional[datetime] = None

_CACHE_TTL_MINUTES = 5


# ── GraphQL wrapper central ────────────────────────────────────────────────────

async def _gql(
    query: str,
    variables: Optional[dict] = None,
    raise_on_error: bool = False,
) -> dict:
    """
    Ejecuta query/mutation contra Twenty CRM (/graphql).
    - Si el circuit breaker está abierto: retorna {} sin intentar.
    - Si raise_on_error=False (default): absorbe errores, retorna {}.
    - Si raise_on_error=True: propaga excepciones (para uso interno crítico).
    """
    if _CircuitBreaker.is_open():
        return {}

    if not TWENTY_API_KEY:
        return {}

    headers = {
        "Authorization": f"Bearer {TWENTY_API_KEY}",
        "Content-Type": "application/json",
    }
    payload: dict = {"query": query}
    if variables:
        payload["variables"] = variables

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=15.0, write=10.0, pool=5.0)) as client:
            resp = await client.post(TWENTY_GQL_URL, json=payload, headers=headers)
            resp.raise_for_status()
            body = resp.json()

        gql_errors = body.get("errors")
        if gql_errors:
            logger.warning(f"[twenty_sync] GraphQL errors: {gql_errors}")
            _CircuitBreaker.record_failure()
            if raise_on_error:
                raise ValueError(f"GraphQL errors: {gql_errors}")
            return {}

        _CircuitBreaker.record_success()
        return body.get("data") or {}

    except httpx.HTTPStatusError as exc:
        logger.warning(f"[twenty_sync] HTTP {exc.response.status_code}: {exc.request.url}")
        _CircuitBreaker.record_failure()
        if raise_on_error:
            raise
        return {}
    except httpx.RequestError as exc:
        logger.warning(f"[twenty_sync] Conexión fallida a Twenty: {exc}")
        _CircuitBreaker.record_failure()
        if raise_on_error:
            raise
        return {}
    except Exception as exc:
        logger.warning(f"[twenty_sync] Error inesperado: {exc}")
        _CircuitBreaker.record_failure()
        if raise_on_error:
            raise
        return {}


# ── Resolvers de catálogos ─────────────────────────────────────────────────────

async def resolver_tipo_documento(clave: str) -> Optional[str]:
    """
    Busca catalogoTipoDocumento por campo 'clave'. Retorna el ID de Twenty o None.
    Cache in-process con TTL de 5 minutos.
    """
    global _cache_tipo_doc, _cache_tipo_doc_ttl

    now = datetime.utcnow()
    cache_expired = _cache_tipo_doc_ttl is None or now > _cache_tipo_doc_ttl

    if cache_expired and not _CircuitBreaker.is_open():
        data = await _gql(
            """
            query GetTiposDoc {
              catalogoTipoDocumentos(first: 50) {
                edges { node { id clave } }
              }
            }
            """
        )
        edges = data.get("catalogoTipoDocumentos", {}).get("edges", [])
        if edges:
            _cache_tipo_doc = {e["node"]["clave"]: e["node"]["id"] for e in edges if e.get("node")}
            _cache_tipo_doc_ttl = now + timedelta(minutes=_CACHE_TTL_MINUTES)

    return _cache_tipo_doc.get(clave)


async def resolver_motivo_rechazo(clave: str) -> Optional[str]:
    """
    Busca motivoRechazo por campo 'clave'. Retorna el ID de Twenty o None.
    Cache in-process con TTL de 5 minutos.
    """
    global _cache_motivo, _cache_motivo_ttl

    now = datetime.utcnow()
    cache_expired = _cache_motivo_ttl is None or now > _cache_motivo_ttl

    if cache_expired and not _CircuitBreaker.is_open():
        data = await _gql(
            """
            query GetMotivos {
              motivoRechazos(first: 50) {
                edges { node { id clave } }
              }
            }
            """
        )
        edges = data.get("motivoRechazos", {}).get("edges", [])
        if edges:
            _cache_motivo = {e["node"]["clave"]: e["node"]["id"] for e in edges if e.get("node")}
            _cache_motivo_ttl = now + timedelta(minutes=_CACHE_TTL_MINUTES)

    return _cache_motivo.get(clave)


# ── Crear documentoAdjunto ─────────────────────────────────────────────────────

async def crear_documento_adjunto(
    nombre_archivo: str,
    url_archivo: str,
    mime_type: str,
    tamano_bytes: int,
    canal_origen: str = "CORREO",
    fecha_recepcion: Optional[str] = None,
    tramite_id: Optional[str] = None,
) -> Optional[str]:
    """
    Crea un documentoAdjunto en Twenty CRM con estatusProcesamiento=PENDIENTE.
    Vincula al tramite si se provee tramite_id.
    Retorna el ID del nuevo objeto o None si falla (no propaga excepción).
    """
    input_data: dict = {
        "name":                   nombre_archivo,
        "nombreArchivo":          nombre_archivo,
        "urlArchivo":             url_archivo,
        "tipoMime":               mime_type,
        "tamanoBytes":            tamano_bytes,
        "canalOrigen":            canal_origen,
        "estatusProcesamiento":   "PENDIENTE",
        "legibilidadIA":          "NO_PROCESADO",
        "estatusEncriptacion":    "VERIFICANDO",
        "esDocumentoDuplicado":   False,
        "fechaRecepcion":         fecha_recepcion or datetime.utcnow().isoformat(),
    }

    if tramite_id:
        input_data["tramite"] = {"connect": {"id": tramite_id}}

    data = await _gql(
        """
        mutation CreateDocAdj($data: DocumentoAdjuntoCreateInput!) {
          createDocumentoAdjunto(data: $data) {
            id
            nombreArchivo
            estatusProcesamiento
          }
        }
        """,
        {"data": input_data},
    )

    doc = data.get("createDocumentoAdjunto") or {}
    doc_id = doc.get("id")
    if doc_id:
        logger.info(f"[twenty_sync] documentoAdjunto creado: {doc_id} ({nombre_archivo})")
    else:
        logger.warning(f"[twenty_sync] No se pudo crear documentoAdjunto para {nombre_archivo}")
    return doc_id


# ── Actualizar encriptación ────────────────────────────────────────────────────

async def actualizar_encriptacion(
    documento_id: str,
    estatus: Literal["SIN_PASSWORD", "CON_PASSWORD", "VERIFICANDO", "ERROR_APERTURA"],
) -> bool:
    """Actualiza estatusEncriptacion de un documentoAdjunto."""
    data = await _gql(
        """
        mutation UpdateEncriptacion($id: ID!, $data: DocumentoAdjuntoUpdateInput!) {
          updateDocumentoAdjunto(id: $id, data: $data) {
            id estatusEncriptacion
          }
        }
        """,
        {"id": documento_id, "data": {"estatusEncriptacion": estatus}},
    )
    return bool(data.get("updateDocumentoAdjunto", {}).get("id"))


# ── Actualizar estatus de procesamiento ───────────────────────────────────────

async def actualizar_estatus_procesamiento(
    documento_id: str,
    estatus: Literal["PENDIENTE", "EN_PROCESO", "PROCESADO", "REQUIERE_REVISION", "ERROR"],
    notas: Optional[str] = None,
) -> bool:
    """
    Actualiza estatusProcesamiento. Si es PROCESADO o REQUIERE_REVISION,
    también registra fechaProcesamiento.
    """
    update: dict = {"estatusProcesamiento": estatus}
    if estatus in ("PROCESADO", "REQUIERE_REVISION", "ERROR"):
        update["fechaProcesamiento"] = datetime.utcnow().isoformat()
    if notas:
        update["notas"] = notas[:500]

    data = await _gql(
        """
        mutation UpdateEstatusProcesamiento($id: ID!, $data: DocumentoAdjuntoUpdateInput!) {
          updateDocumentoAdjunto(id: $id, data: $data) {
            id estatusProcesamiento
          }
        }
        """,
        {"id": documento_id, "data": update},
    )
    return bool(data.get("updateDocumentoAdjunto", {}).get("id"))


# ── Calcular legibilidad ───────────────────────────────────────────────────────

def calcular_legibilidad(
    texto_extraido: str,
    confidence: int,
    metodo_extraccion: str,
) -> tuple[Literal["LEGIBLE", "PARCIALMENTE_LEGIBLE", "ILEGIBLE", "NO_PROCESADO", "ERROR_OCR"], int]:
    """
    Mapea resultado del pipeline → enum legibilidadIA + puntuación 0-100.

    Reglas:
      - texto vacío                        → ERROR_OCR, puntuacion=0
      - confidence >= 80 y texto > 200c    → LEGIBLE
      - confidence >= 50                   → PARCIALMENTE_LEGIBLE
      - confidence < 50 y texto no vacío   → ILEGIBLE
    """
    if not texto_extraido or not texto_extraido.strip():
        return "ERROR_OCR", 0

    if confidence >= 80 and len(texto_extraido) > 200:
        return "LEGIBLE", confidence
    elif confidence >= 50:
        return "PARCIALMENTE_LEGIBLE", confidence
    else:
        return "ILEGIBLE", confidence


# ── Actualizar con resultado de IA ─────────────────────────────────────────────

async def actualizar_con_resultado_ia(
    documento_id: str,
    tipo_documento_clave: str,
    texto_extraido: str,
    legibilidad: Literal["LEGIBLE", "PARCIALMENTE_LEGIBLE", "ILEGIBLE", "NO_PROCESADO", "ERROR_OCR"],
    puntuacion_legibilidad: int,
    metadatos_ia: dict,
    hash_validacion: Optional[str] = None,
    motivo_rechazo_clave: Optional[str] = None,
    confidence: int = 0,
) -> bool:
    """
    Actualiza documentoAdjunto con resultado completo del procesamiento IA.
    - Resuelve tipo_documento_clave → ID de catalogoTipoDocumento
    - Resuelve motivo_rechazo_clave → ID de motivoRechazo (si aplica)
    - Determina estatusProcesamiento: PROCESADO o REQUIERE_REVISION (si confianza < 60)
    """
    import json as _json

    tipo_doc_id = await resolver_tipo_documento(tipo_documento_clave)
    motivo_id = None
    if motivo_rechazo_clave:
        motivo_id = await resolver_motivo_rechazo(motivo_rechazo_clave)

    # Documentos con confianza baja o tipo "Otro" requieren revisión manual
    estatus_final = (
        "REQUIERE_REVISION"
        if (confidence < 60 or tipo_documento_clave == "OTRO")
        else "PROCESADO"
    )

    update: dict = {
        "textoExtraido":          texto_extraido[:10_000] if texto_extraido else "",
        "legibilidadIA":          legibilidad,
        "puntuacionLegibilidad":  puntuacion_legibilidad,
        "metadatosIA":            _json.dumps(metadatos_ia, ensure_ascii=False)[:5000],
        "estatusProcesamiento":   estatus_final,
        "fechaProcesamiento":     datetime.utcnow().isoformat(),
    }

    if hash_validacion:
        update["hashValidacion"] = hash_validacion

    if tipo_doc_id:
        update["tipoDocumento"] = {"connect": {"id": tipo_doc_id}}
    else:
        logger.warning(
            f"[twenty_sync] No se encontró catalogoTipoDocumento con clave '{tipo_documento_clave}'"
        )

    if motivo_id:
        update["motivoRechazo"] = {"connect": {"id": motivo_id}}

    data = await _gql(
        """
        mutation UpdateResultadoIA($id: ID!, $data: DocumentoAdjuntoUpdateInput!) {
          updateDocumentoAdjunto(id: $id, data: $data) {
            id estatusProcesamiento legibilidadIA
          }
        }
        """,
        {"id": documento_id, "data": update},
    )

    result = data.get("updateDocumentoAdjunto") or {}
    success = bool(result.get("id"))
    if success:
        logger.info(
            f"[twenty_sync] Doc {documento_id} → {estatus_final} "
            f"(tipo={tipo_documento_clave}, legibilidad={legibilidad}, confianza={confidence})"
        )
    return success


# ── Registrar historialEstatus ─────────────────────────────────────────────────

async def registrar_historial_estatus(
    entidad_tipo: str,
    entidad_id: str,
    estatus_anterior: str,
    estatus_nuevo: str,
    tramite_id: Optional[str] = None,
    motivo_cambio: Optional[str] = None,
    cambio_automatico: bool = True,
    tiempo_transcurrido_minutos: Optional[int] = None,
    metadatos: Optional[dict] = None,
) -> Optional[str]:
    """
    Crea un registro en historialEstatus en Twenty CRM.
    Retorna el ID del registro creado o None si falla.
    """
    import json as _json

    input_data: dict = {
        "name":            f"{entidad_tipo}: {estatus_anterior} → {estatus_nuevo}",
        "entidadTipo":     entidad_tipo,
        "entidadId":       entidad_id,
        "estatusAnterior": estatus_anterior,
        "estatusNuevo":    estatus_nuevo,
        "fechaCambio":     datetime.utcnow().isoformat(),
        "cambioAutomatico": cambio_automatico,
    }

    if motivo_cambio:
        input_data["motivoCambio"] = motivo_cambio[:500]
    if tiempo_transcurrido_minutos is not None:
        input_data["tiempoTranscurridoMinutos"] = tiempo_transcurrido_minutos
    if metadatos:
        input_data["metadatos"] = _json.dumps(metadatos, ensure_ascii=False)[:2000]
    if tramite_id:
        input_data["tramite"] = {"connect": {"id": tramite_id}}

    data = await _gql(
        """
        mutation CreateHistorial($data: HistorialEstatusCreateInput!) {
          createHistorialEstatus(data: $data) {
            id fechaCambio
          }
        }
        """,
        {"data": input_data},
    )

    historial = data.get("createHistorialEstatus") or {}
    return historial.get("id")


# ── Vincular documentoAdjunto a tramite ───────────────────────────────────────

# ── HiloConversacion ──────────────────────────────────────────────────────────

async def buscar_hilo_por_thread_id(thread_id: str) -> Optional[dict]:
    """
    Busca un HiloConversacion en Twenty por su threadExternalId.
    Retorna el nodo completo (con tramiteId y agenteId si existen) o None.
    Usa _gql con circuit breaker — nunca propaga excepción.
    """
    if not thread_id:
        return None

    data = await _gql(
        """
        query BuscarHiloPorThread($filter: HiloConversacionFilterInput) {
          hilosConversacion(filter: $filter, first: 1) {
            edges {
              node {
                id
                asunto
                estatusHilo
                mensajesCount
                requiereAccion
                tramite { id folioInterno estadoTramite }
                agente { id name { firstName lastName } }
              }
            }
          }
        }
        """,
        {"filter": {"threadExternalId": {"eq": thread_id}}},
    )
    edges = data.get("hilosConversacion", {}).get("edges", [])
    if not edges:
        return None
    node = edges[0].get("node") or {}
    # Normalizar para acceso directo
    tramite = node.get("tramite") or {}
    agente  = node.get("agente") or {}
    node["tramiteId"] = tramite.get("id")
    node["agenteId"]  = agente.get("id")
    return node


async def crear_hilo_conversacion(
    asunto: str,
    thread_external_id: str,
    canal_origen: str,
    ultimo_mensaje_en: str,
    ultimo_remitente: str,
    mensajes_count: int,
    requiere_accion: bool,
    tramite_id: Optional[str] = None,
    agente_id: Optional[str] = None,
) -> Optional[str]:
    """
    Crea un nuevo HiloConversacion en Twenty CRM.
    Retorna el UUID del objeto creado o None si falla.
    canal_origen: 'CORREO' | 'WHATSAPP'
    ultimo_remitente: 'AGENTE' | 'ANALISTA'
    """
    input_data: dict = {
        "name":              asunto[:500],
        "asunto":            asunto[:500],
        "threadExternalId":  thread_external_id,
        "canalOrigen":       canal_origen,
        "ultimoMensajeEn":   ultimo_mensaje_en,
        "ultimoRemitente":   ultimo_remitente,
        "mensajesCount":     mensajes_count,
        "requiereAccion":    requiere_accion,
        "estatusHilo":       "ACTIVO",
    }
    if tramite_id:
        input_data["tramite"] = {"connect": {"id": tramite_id}}
    if agente_id:
        input_data["agente"] = {"connect": {"id": agente_id}}

    data = await _gql(
        """
        mutation CrearHilo($data: HiloConversacionCreateInput!) {
          createHiloConversacion(data: $data) {
            id asunto estatusHilo
          }
        }
        """,
        {"data": input_data},
    )
    hilo = data.get("createHiloConversacion") or {}
    hilo_id = hilo.get("id")
    if hilo_id:
        logger.info(f"[twenty_sync] HiloConversacion creado: {hilo_id} ({asunto[:60]!r})")
    else:
        logger.warning(f"[twenty_sync] No se pudo crear HiloConversacion para thread {thread_external_id!r}")
    return hilo_id


async def actualizar_hilo_conversacion(
    hilo_id: str,
    ultimo_mensaje_en: str,
    ultimo_remitente: str,
    incrementar_mensajes: bool = True,
    requiere_accion: Optional[bool] = None,
    estatus_hilo: Optional[str] = None,
    tramite_id: Optional[str] = None,
) -> bool:
    """
    Actualiza un HiloConversacion existente.

    - Siempre actualiza ultimoMensajeEn y ultimoRemitente.
    - Si incrementar_mensajes=True, suma 1 al contador (requiere leer antes).
    - Solo actualiza requiereAccion y estatusHilo si se pasan explícitamente.
    - Solo actualiza tramite si se pasa (para vincular cuando se resuelve el matching).
    """
    # Leer mensajesCount actual si hay que incrementar
    mensajes_count: Optional[int] = None
    if incrementar_mensajes:
        current = await _gql(
            """
            query GetHiloCount($id: ID!) {
              hiloConversacion(id: $id) { mensajesCount }
            }
            """,
            {"id": hilo_id},
        )
        actual = (current.get("hiloConversacion") or {}).get("mensajesCount") or 0
        mensajes_count = actual + 1

    update: dict = {
        "ultimoMensajeEn":  ultimo_mensaje_en,
        "ultimoRemitente":  ultimo_remitente,
    }
    if mensajes_count is not None:
        update["mensajesCount"] = mensajes_count
    if requiere_accion is not None:
        update["requiereAccion"] = requiere_accion
    if estatus_hilo is not None:
        update["estatusHilo"] = estatus_hilo
    if tramite_id is not None:
        update["tramite"] = {"connect": {"id": tramite_id}}

    data = await _gql(
        """
        mutation ActualizarHilo($id: ID!, $data: HiloConversacionUpdateInput!) {
          updateHiloConversacion(id: $id, data: $data) {
            id mensajesCount ultimoRemitente
          }
        }
        """,
        {"id": hilo_id, "data": update},
    )
    ok = bool((data.get("updateHiloConversacion") or {}).get("id"))
    if ok:
        logger.info(f"[twenty_sync] HiloConversacion {hilo_id} actualizado")
    return ok


async def buscar_tramites_activos_por_agente(agente_id: str) -> list[dict]:
    """
    Retorna lista de trámites activos (estados que no son RESUELTO/CANCELADO)
    de un agente. Ordenados por fechaEntrada descendente.
    Máximo 50 resultados (suficiente para desambiguación por LLM).
    """
    if not agente_id:
        return []

    _ESTADOS_INACTIVOS = ["RESUELTO", "CANCELADO"]
    filtros = [
        {"agenteTitularId": {"eq": agente_id}},
        {"estadoTramite": {"not": {"in": _ESTADOS_INACTIVOS}}},
    ]

    data = await _gql(
        """
        query TramitesActivosAgente($filter: TramiteFilterInput) {
          tramites(
            filter: $filter
            orderBy: { fechaEntrada: DescNullsLast }
            first: 50
          ) {
            edges {
              node {
                id
                folioInterno
                tipoTramite
                ramo
                estadoTramite
                numPolizaGnp
                nombreAsegurado
                fechaEntrada
              }
            }
          }
        }
        """,
        {"filter": {"and": filtros}},
    )
    edges = data.get("tramites", {}).get("edges", [])
    return [e["node"] for e in edges if e.get("node")]


async def buscar_tramite_por_folio(folio: str) -> Optional[dict]:
    """
    Busca un Trámite en Twenty por su folioInterno (exacto, case-insensitive).
    Retorna el nodo con id y estado, o None.
    """
    if not folio:
        return None
    data = await _gql(
        """
        query TramitePorFolio($filter: TramiteFilterInput) {
          tramites(filter: $filter, first: 1) {
            edges {
              node {
                id folioInterno estadoTramite tipoTramite ramo
                agenteTitular { id }
              }
            }
          }
        }
        """,
        {"filter": {"folioInterno": {"ilike": folio}}},
    )
    edges = data.get("tramites", {}).get("edges", [])
    if not edges:
        return None
    return edges[0].get("node")


async def buscar_tramite_por_poliza(num_poliza: str) -> Optional[dict]:
    """
    Busca un Trámite en Twenty por su numPolizaGnp.
    Retorna el nodo más reciente (puede haber endosos de la misma póliza), o None.
    """
    if not num_poliza:
        return None
    data = await _gql(
        """
        query TramitePorPoliza($filter: TramiteFilterInput) {
          tramites(
            filter: $filter
            orderBy: { fechaEntrada: DescNullsLast }
            first: 1
          ) {
            edges {
              node {
                id folioInterno numPolizaGnp estadoTramite tipoTramite ramo
                agenteTitular { id }
              }
            }
          }
        }
        """,
        {"filter": {"numPolizaGnp": {"eq": num_poliza}}},
    )
    edges = data.get("tramites", {}).get("edges", [])
    if not edges:
        return None
    return edges[0].get("node")


async def escalar_prioridad_tramite(tramite_id: str, motivo: str = "") -> bool:
    """
    Escala la prioridad de un trámite a URGENTE si no lo estaba ya.
    Se llama cuando se detecta lenguaje de urgencia en el email.
    No modifica si el trámite ya está en URGENTE.
    """
    # Leer prioridad actual
    current = await _gql(
        """
        query GetPrioridad($id: ID!) {
          tramite(id: $id) { id prioridad }
        }
        """,
        {"id": tramite_id},
    )
    prioridad_actual = (current.get("tramite") or {}).get("prioridad")
    if prioridad_actual == "URGENTE":
        return True  # ya está escalado

    notas_update = f"[AUTO] Prioridad escalada a URGENTE — {motivo}" if motivo else ""

    data = await _gql(
        """
        mutation EscalarPrioridad($id: ID!, $data: TramiteUpdateInput!) {
          updateTramite(id: $id, data: $data) {
            id prioridad
          }
        }
        """,
        {"id": tramite_id, "data": {"prioridad": "URGENTE", "notasAnalista": notas_update}},
    )
    ok = bool((data.get("updateTramite") or {}).get("id"))
    if ok:
        logger.info(f"[twenty_sync] Tramite {tramite_id} escalado a URGENTE")
    return ok


# ── Vincular documentoAdjunto a tramite ───────────────────────────────────────

async def vincular_documento_a_tramite(documento_id: str, tramite_id: str) -> bool:
    """
    Actualiza la relación tramite de un documentoAdjunto existente.
    Se usa cuando el Agente 4 crea el tramite después de que los documentos ya existen.
    """
    data = await _gql(
        """
        mutation VincularDocTramite($id: ID!, $data: DocumentoAdjuntoUpdateInput!) {
          updateDocumentoAdjunto(id: $id, data: $data) {
            id
          }
        }
        """,
        {"id": documento_id, "data": {"tramite": {"connect": {"id": tramite_id}}}},
    )
    return bool((data.get("updateDocumentoAdjunto") or {}).get("id"))
