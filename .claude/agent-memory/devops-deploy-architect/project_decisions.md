---
name: Decisiones de infraestructura y sus razones
description: Por qué se eligió cada plataforma y restricciones conocidas
type: project
---

# Decisiones de infraestructura

## Railway para FastAPI
**Decisión**: FastAPI corre en Railway (no en el VPS)
**Why**: Scaling automático, deploys desde GitHub sin gestión de servidor, Railway maneja SSL.
**How to apply**: Al hablar de deploys de FastAPI, siempre es Railway. No confundir con el VPS.

## VPS propio para Twenty CRM y n8n
**Decisión**: Twenty CRM y n8n corren en Docker en un VPS propio
**Why**: Twenty CRM es un fork personalizado con objetos custom y dashboard embebido.
No cabe bien en plataformas PaaS por el volumen de datos y necesidad de PostgreSQL + Redis propio.
n8n también necesita persistencia y se mantiene simple en el mismo servidor.
**How to apply**: Cambios a Twenty siempre implican deploy al VPS via SSH o CI/CD con SSH action.

## Supabase para persistencia del pipeline
**Decisión**: Supabase (no la PostgreSQL de Twenty) guarda los datos del pipeline de ingesta
**Why**: Twenty CRM tiene su propia BD interna. Los datos intermedios del pipeline
(incoming_emails, tramites_pipeline, ocr_results) viven en Supabase para que FastAPI
pueda acceder sin pasar por el GraphQL de Twenty.
**How to apply**: Hay DOS bases de datos: la interna de Twenty (PostgreSQL en Docker)
y la de Supabase (pipeline). No confundirlas al diseñar queries o migraciones.

## GNP no tiene API pública
**Decisión**: El turno a GNP es manual
**Why**: GNP no expone API. El analista sube documentos al portal de GNP manualmente
y luego registra el folioGnp en Twenty CRM.
**How to apply**: No proponer integraciones automáticas con GNP — no es posible técnicamente.

## Vercel para dashboard únicamente
**Decisión**: Vercel solo sirve el dashboard custom (DashboardPage.tsx con DirectoraView/GerenteView/EspecialistaView)
**Why**: El dashboard lee datos de Supabase directamente via anon key + RLS.
Twenty CRM sigue siendo la fuente de verdad para los analistas.
**How to apply**: Variables VITE_ en Vercel solo incluyen anon key de Supabase, nunca service_role.
