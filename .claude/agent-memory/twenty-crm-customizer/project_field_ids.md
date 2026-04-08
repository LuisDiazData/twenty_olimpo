---
name: Field metadata IDs de objetos Hypnos
description: IDs de todos los campos de metadatos de los objetos tramite y agente para uso en filtros, sorts y viewFields
type: project
---

# Field Metadata IDs — Hypnos Twenty CRM

Instancia: `http://localhost:3000`  
API Key en uso: header `Authorization: Bearer <token>` (ver scripts existentes)

**Why:** Los filtros, sorts y viewFields de las vistas requieren `fieldMetadataId`, no el nombre del campo. Tener estos IDs evita consultar la metadata API cada vez.

**How to apply:** Usar directamente al crear filtros, sorts o campos de vistas. Verificar con `getViewFields(viewId)` si hay dudas sobre cambios.

---

## Objeto: tramite
`objectMetadataId: f64ac7de-951d-4d46-9f51-6456310bc1e9`

| Campo | fieldMetadataId | Tipo |
|-------|----------------|------|
| name | 71c78086-cfd3-4401-a0cc-2264c64c96d6 | TEXT |
| folio (Folio Interno) | 414e2440-5109-4852-9f11-283e3a87abeb | TEXT |
| folioGnp | edbf5546-6dba-4bbb-98d1-78cf134f3fff | TEXT |
| numeroPoliza | c689ce38-a0c6-42f4-bda6-c386d734c76b | TEXT |
| estatus | cecbfb12-552e-460a-a706-42c62daa17d3 | SELECT |
| ramo | a3c91599-ebe5-4070-8dd9-17a19ff1b00f | SELECT |
| tipoTramite | 10df70ae-59de-4b27-b27b-f2091985df2a | SELECT |
| prioridad | 5289a07b-9108-4dd0-b42b-383a49985240 | SELECT |
| canalIngreso | 275212b3-3e7c-4145-bcf7-570c5245ec40 | SELECT |
| fechaIngreso | 9c9d783c-a224-4091-a0f8-9365d4a99d81 | DATE_TIME |
| fechaLimiteDocumentacion | 198997df-535b-441e-999c-462368cb7828 | DATE |
| fechaTurnoGnp | 5ce864e2-75c1-4712-9015-f1fbd3ecbc9f | DATE_TIME |
| fechaResolucion | 3eeb144f-ead8-4383-8d53-218a28d20696 | DATE_TIME |
| motivoDetencion | 162b66c1-cb3c-4d83-a034-0407b648c8ca | RICH_TEXT |
| notasInternas | 956ad9ae-8f8f-40fe-ab71-8c93ec40a7ce | RICH_TEXT |
| monto | e6ae0c1f-268f-4246-ac88-23173b7d7401 | CURRENCY |
| agente (RELATION) | 94b406b9-d138-483b-ad9c-37783a58d520 | RELATION |
| analistaAsignado (RELATION) | bbb213ce-d920-490d-b61f-e825cdc5c067 | RELATION |
| gerenteRamo (RELATION) | dfa6e3a0-45fa-4f58-bfd9-146d945698d7 | RELATION |
| asegurado (RELATION) | 5859e3d9-7ed0-46fa-8de5-7098c5a32453 | RELATION |
| createdAt | 77e030ab-a542-4f50-bc48-d68f098bedf3 | DATE_TIME |

---

## Objeto: agente
`objectMetadataId: eea61f1e-ef36-458c-9982-36d31f478b8f`

| Campo | fieldMetadataId | Tipo |
|-------|----------------|------|
| name | 1030ea77-35eb-4134-940a-42b76d079df8 | TEXT |
| claveAgente | c357064a-a1fe-4f5d-90da-ac284c20491e | TEXT |
| celular | dad10e9d-31a4-4ee6-bb39-26c86db109e3 | PHONES |
| email | 14c8be9c-ebd1-444c-bbbb-afe1f5aa219a | EMAILS |
| ramos | dcabbae5-8661-418d-ab8b-b3dbb58f3903 | MULTI_SELECT |
| activo | a59006b9-1ec3-43e0-8d7f-05aa1859a587 | BOOLEAN |
| nivel | 2eba9804-c08e-4553-9ae6-98a79bede77f | SELECT |
| tipoPersona | 54267731-c18d-4f84-93e3-b28e24e63a08 | SELECT |
| gerenteDesarrollo | 9563bbe4-f53c-42da-a85f-1e69d42c2077 | RELATION |
| promotoriaAsignada | cc511058-6f6c-414e-9819-fc8ce52659e4 | TEXT |
| cedula | 44387bba-c780-453c-875b-ccb42cbdbf88 | TEXT |
| rfc | cd4160af-3a37-4de6-ab01-649cc5ec8d38 | TEXT |
| fechaAlta | a6694913-c955-4051-844d-76896dd49d78 | DATE |
| fechaVencimientoCedula | 62713234-90fe-40c9-9e75-b72f50c54eca | DATE |
| createdAt | b4892859-9b38-4c5f-8fcc-ea9c314ecf6c | DATE_TIME |

---

## Objeto: tramite (campos adicionales — 2026-04-03)

| Campo | fieldMetadataId | Tipo |
|-------|----------------|------|
| slaHoras | 6c72e543-b82b-4ea6-a41e-cce277a39aac | NUMBER |
| ubicacionTramite | 30f7f31f-53e8-43a6-ae2f-4063e527cbf5 | SELECT |
| poliza (RELATION) | 3306b383-7511-457c-8d6f-3bc2af64ecc6 | RELATION |

---

## Objeto: poliza
`objectMetadataId: 0304e996-a780-4b53-b53a-b127ee51dbe6`

| Campo | fieldMetadataId | Tipo |
|-------|----------------|------|
| numeroPoliza | 45db5a0d-cc3d-40c3-a1ea-b878dffcc792 | TEXT |
| fechaInicioVigencia | d4b58451-d87f-48f5-9840-9aa78345b2eb | DATE |
| fechaFinVigencia | 41a73e04-64c2-47f0-a393-355659dfa7d5 | DATE |
| aseguradoPrincipal | a51c17bf-344c-4ff1-b461-52e730de29d0 | TEXT |
| notas | b16efe2e-3f35-4c9d-a3f6-9f6e58aba959 | RICH_TEXT |
| ramo | b7017b7c-077b-432d-aa99-452e96a052a8 | SELECT |
| tipoPoliza | 3c2822ee-3170-4e8b-acbe-177c0789073e | SELECT |
| estatus | 955d9727-54f2-40f0-b128-79ab6c5c3f26 | SELECT |
| primaTotal | 2451cc1a-60ef-4fb6-96b0-3bb419b43253 | CURRENCY |
| primaNeta | 8ea8b247-3c1e-47d2-9f60-6612122e9253 | CURRENCY |
| conductoCobro | 345668c8-6f68-4acc-8f2b-0baf093f97dc | SELECT |
| periodicidadPago | e538c95e-5c03-4e24-ac47-c8322056c60e | SELECT |
| sumaAsegurada | 158a09fb-0773-464c-ac6f-e484071f678b | CURRENCY |
| agente (RELATION) | 748eb65c-3659-47a1-b837-533f38be9f9e | RELATION |

---

## Objeto: siniestro
`objectMetadataId: cd74d2f5-428b-4782-b80f-e4fe8720f8ab`

| Campo | fieldMetadataId | Tipo |
|-------|----------------|------|
| folioSiniestro | 4de7a997-3ad9-4ee0-a966-b0a0569708b5 | TEXT |
| folioInterno | b44d91f0-b01f-4bde-bb49-405cd6c29f2d | TEXT |
| ramo | 1c3f4ab5-ee1e-4b97-a351-920bbc56842b | SELECT |
| tipoSiniestro | 77dd01bf-013f-47bb-8567-017c79353e44 | SELECT |
| estatus | e5857cf3-2c9b-4834-bb06-458739f31cc5 | SELECT |
| fechaOcurrencia | fc8354d1-7952-422e-b68c-1bb0a3165e9e | DATE |
| fechaReporte | 3770bec3-9958-49ab-88d8-3ef2d02d1ef0 | DATE_TIME |
| fechaReporteGnp | a7436971-fe61-49b9-add4-1d5d6955b87e | DATE_TIME |
| montoEstimado | 76df3d8a-08b0-4078-aa53-8de122710222 | CURRENCY |
| montoAprobado | 49968ec3-6ca6-4f7c-9f83-574fb71fcfc7 | CURRENCY |
| montoLiquidado | 9195d450-a918-4f9f-be56-a6d3f9e400b8 | CURRENCY |
| dictamen | 5926c962-c44c-447f-af7d-ece3afaad291 | RICH_TEXT |
| descripcionSiniestro | 8b3b8619-23c6-41fb-b6d5-b43d53186f8d | RICH_TEXT |
| ajustadorAsignado | 1ab04770-d4c2-4a2f-91d9-8e47f58ff478 | TEXT |
| numeroAjustador | a7367ea7-aa98-4ce9-a432-fd8d5f8fa0e8 | TEXT |
| motivoRechazo | cb7f34ef-7312-4408-ab6a-8fcbd087db86 | RICH_TEXT |
| documentacionMedica | d357d0fc-7156-4601-b063-b4cf80d4a3c7 | RICH_TEXT |
| notas | ee128eda-88f9-4efd-8288-d3cefe553e4e | RICH_TEXT |
| poliza (RELATION) | 9b827c08-011f-406f-a5e1-c266b549b4bc | RELATION |
| tramite (RELATION) | 7f642240-4a1e-4874-ae5b-927babb71d69 | RELATION |
| agente (RELATION) | 75ee2970-51ca-4a97-827c-7307fb7de2d3 | RELATION |

---

## Objeto: endoso
`objectMetadataId: 6d242c94-ba00-40f8-84c1-4d99f99d2b46`

| Campo | fieldMetadataId | Tipo |
|-------|----------------|------|
| folioEndoso | 5c451821-7f6c-4cb1-8593-75d0116d2d18 | TEXT |
| tipoEndoso | 8195c91e-8ca9-4343-b19f-8d7e38a83f3f | SELECT |
| motivoCambio | effb6a2f-0887-4976-8d43-68edda14d96a | SELECT |
| descripcionCambio | e1b97d73-2d0b-4192-a6af-ec9e59a07b2d | RICH_TEXT |
| estatusAplicacion | 9255b93c-82a6-4300-91a7-f892ac50316d | SELECT |
| fechaSolicitud | 21696edf-0eaa-4df4-b5c7-b7b77c0f3318 | DATE_TIME |
| fechaAplicacion | e9e9cdb7-1d09-4677-8eec-a2692a8ca41b | DATE_TIME |
| folioGnpEndoso | 5c4cae6a-7e1a-4b3e-9a26-7caacc924bef | TEXT |
| motivoRechazo | 82b1b841-bac6-4c30-aaa0-b319ba04447b | TEXT |
| notas | 3c728d8a-8cf9-4f32-ad51-4b285e58a89e | RICH_TEXT |
| poliza (RELATION) | 8ddd9bcc-efe6-4bdf-b731-ad1ec84aac38 | RELATION |
| tramite (RELATION) | 19666723-da28-4ad8-abca-a983fe967634 | RELATION |

---

## Otros objetos custom

| Objeto | objectMetadataId |
|--------|----------------|
| documentoTramite | e9ae6e8a-1252-4693-841c-026788c2ad62 |
| alertaTramite | 42b35181-59cc-4318-8455-67698a3dac05 |
| asegurado | c158577d-bfa5-4216-af23-2d8766ea3914 |
| colaborador | 9acbd717-d9d9-4991-b39b-1e19d8e1dc29 |
| workspaceMember | a1565864-e88a-4edb-a081-0fd173a05151 |

---

## Capa III — Documentación e Inteligencia (creados 2026-04-03)

### Objeto: catalogoTipoDocumento
`objectMetadataId: e8e8af70-f2b9-45ba-a772-1e60fec318dc`

| Campo | fieldMetadataId | Tipo |
|-------|----------------|------|
| clave | 05fcf81f-da1f-4af0-9df4-2352db565d65 | TEXT |
| nombre | 4339762b-a9db-47f1-802b-008f432dce0e | TEXT |
| ramo | d03aed92-2e19-4258-8f5b-3ff2dde45e4c | SELECT |
| tipoTramite | b30106be-cf75-4a37-a910-fe36871b117a | SELECT |
| esObligatorio | 79d85aa3-4dc2-45e0-bd80-dc123039fed9 | BOOLEAN |
| activo | baed5827-20b4-4bb0-9838-8a8f2bc7226f | BOOLEAN |
| ejemploUrl | e1100396-5858-41ab-90b9-5fc5eacb5d29 | TEXT |
| descripcion | 40a4afe8-5204-409a-9094-f1ef44f9de51 | RICH_TEXT |
| instruccionesValidacion | bdaa7dbb-6620-48c0-ac55-790251da83b1 | RICH_TEXT |

---

### Objeto: motivoRechazo
`objectMetadataId: f40fcfba-6a9d-46be-b93e-87a27e7f17c1`

| Campo | fieldMetadataId | Tipo |
|-------|----------------|------|
| clave | 02dc33ec-0657-41c7-b73d-9cb3d6975c0c | TEXT |
| descripcion | 2edb0555-cccf-45e7-8cfa-ef2e4f56e50d | TEXT |
| codigoGnp | b2f01847-ddf3-42a5-a84e-8603f35a8f8b | TEXT |
| categoria | 97ee0423-d40a-4816-9aa4-e66ec99a8206 | SELECT |
| ramo | adf2ff08-c66c-4db4-8010-9a46ad2c2bae | SELECT |
| tipoTramite | bc1099d4-d4df-403b-a815-105485940eff | SELECT |
| accionRecomendada | 67844624-d298-498b-91ac-0441bbbf6995 | RICH_TEXT |
| tiempoEstimadoSubsanacionHoras | ddc27dde-1e38-482e-88a0-b5fec610f89c | NUMBER |
| frecuencia | 32ef5db7-d759-46c9-a2e1-3131d629b3b3 | NUMBER |
| esRechazoGnp | 73ae08e5-ac88-4f08-a50b-2a4c4d5a9925 | BOOLEAN |
| activo | 2ab8017d-8e0d-4663-8541-1381406aca05 | BOOLEAN |

---

### Objeto: documentoAdjunto
`objectMetadataId: ada8c39a-c392-4a10-a237-d227ab073808`

| Campo | fieldMetadataId | Tipo |
|-------|----------------|------|
| nombreArchivo | f373d4b8-d5d8-4c92-b1a4-f1d02a0bc5dd | TEXT |
| urlArchivo | bfeb1387-012f-4eee-8320-f0c76a458894 | TEXT |
| hashValidacion | 5ffc17b3-eacb-49f9-821d-9100c206440a | TEXT |
| tipoMime | fba41907-ec58-416c-8fb7-ed5578c48892 | TEXT |
| notas | 5899ab54-ab23-4a9b-a3ff-a53cf277b8dd | TEXT |
| tamanoBytes | 64f6436b-0fba-4ea2-8f4a-3a9837ce2977 | NUMBER |
| puntuacionLegibilidad | 7ce9cf5f-0d79-4cc2-be99-4e32680f4dd1 | NUMBER |
| estatusEncriptacion | 7e2da7b2-9c1e-49ed-9ed5-56f5aceebc23 | SELECT |
| legibilidadIA | e64071e4-548e-472c-9a56-4b576ec524e6 | SELECT |
| estatusProcesamiento | dfa88a93-5e6a-4d00-9a54-e67d9c119048 | SELECT |
| canalOrigen | 162479c8-82f7-4cfd-9011-44467b1b74f7 | SELECT |
| textoExtraido | 9a11cb05-47a5-4e4f-aaf9-a22d36ac2ea0 | RICH_TEXT |
| metadatosIA | c095aeaa-a0da-4986-bfa1-d7ac4d6b747d | RICH_TEXT |
| fechaRecepcion | 01de8183-533e-428c-a22c-9befa3935f96 | DATE_TIME |
| fechaProcesamiento | 362040e0-e8c4-46a1-8589-fa00eac49879 | DATE_TIME |
| esDocumentoDuplicado | 2b9b342c-f375-414f-83c1-522b5fbd95ed | BOOLEAN |
| tramite (RELATION) | c31ac60a-34bd-4fad-a409-7f97ba81a6df | RELATION |
| tipoDocumento (RELATION → catalogoTipoDocumento) | e8b4210d-0b8a-4df6-85cb-a1731a996da6 | RELATION |
| motivoRechazo (RELATION → motivoRechazo) | 2a09bdac-d179-42d1-909b-cda1818585a4 | RELATION |

---

### Objeto: historialEstatus
`objectMetadataId: 0000d3e4-b914-4c20-abeb-f0f0e47395be`
`namePlural: historialEstatusLogs` (singular y plural debían ser distintos)

| Campo | fieldMetadataId | Tipo |
|-------|----------------|------|
| entidadTipo | 0708d0cd-1895-4a12-a874-2dfae21dbe05 | SELECT |
| entidadId | 0e5647f0-7dc0-45bd-851d-8610d9741cc4 | TEXT |
| estatusAnterior | adb9a218-2c94-421a-865d-4c3a87042ca0 | TEXT |
| estatusNuevo | c55353a7-af27-4748-b625-cb936372f8a4 | TEXT |
| motivoCambio | 900f327d-b95b-438d-a91f-0bff4e08f542 | TEXT |
| ipOrigen | a15c2e63-4172-43dc-b907-ba00d517ed39 | TEXT |
| notas | d563fe13-792e-4e9e-8606-5d21f7f99679 | TEXT |
| responsable | a17a2f3f-c755-4c80-87c2-1d4af8288d5a | TEXT |
| fechaCambio | b4c19c55-f4c7-4af5-a398-13807a10447a | DATE_TIME |
| tiempoTranscurridoMinutos | e4f2947f-71ba-4398-a763-3e64ff141cf5 | NUMBER |
| cambioAutomatico | fc7f854b-f76b-424f-ae32-093fdb08d4f7 | BOOLEAN |
| metadatos | 756e2522-ed96-4a54-a5ff-5df86ec347d7 | RICH_TEXT |
| tramite (RELATION) | ffbe0a96-177d-4273-b20b-c49f74c066d3 | RELATION |

---

## Objeto: hiloConversacion
`objectMetadataId: d3804403-5919-486b-bb7b-2b5c76825e63`

| Campo | fieldMetadataId | Tipo |
|-------|----------------|------|
| name | 5c01b169-7ffa-45ad-b1aa-2b6cf9b2fbb0 | TEXT |
| asunto | 0bf3b474-4f4b-4454-abfa-1f69f5b0a251 | TEXT |
| threadExternalId | 830e31b7-e351-404d-8c7d-0facf3ffcab8 | TEXT |
| canalOrigen | 8f6c0098-61cc-4eb3-b83d-0054c110961c | SELECT |
| estatusHilo | f6b5881a-2fb2-43a1-b81e-4929628004ad | SELECT |
| ultimoMensajeEn | 125205dc-58b2-4d57-b617-ce3a9c580121 | DATE_TIME |
| ultimoRemitente | 48f69b55-53d5-4dd6-89e1-e73c860e35f4 | SELECT |
| mensajesCount | 20053f7e-2d9b-451b-bc39-6c11a01df759 | NUMBER |
| requiereAccion | bc40c58d-8542-4a89-8d45-f3ded928bfa1 | BOOLEAN |
| tramite (RELATION → tramite) | aea457d3-3695-41c0-b186-bb596d98c4c0 | RELATION |
| agente (RELATION → agente) | 3c05390e-6d5e-4095-a67a-51420e86fd3a | RELATION |
| createdAt | b58c5cff-9b0c-41d0-93f4-b31d10277b28 | DATE_TIME |

Notas:
- El lado inverso en tramite se llama `hilosConversacion` (fieldName en tramite)
- El lado inverso en agente se llama `hilosConversacion` (fieldName en agente)
- `canalOrigen` opciones: CORREO, WHATSAPP
- `estatusHilo` opciones: ACTIVO, ESPERANDO_RESPUESTA, CERRADO
- `ultimoRemitente` opciones: AGENTE, ANALISTA
