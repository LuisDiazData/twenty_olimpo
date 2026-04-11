# Guía Definitiva de Producción: InsuraCRM AI (Proyecto "Un Millón de Dólares")

Este documento es el **Manual Operativo y de Arquitectura en Producción** para llevar el proyecto "Twenty Olimpo" (InsuraCRM AI) a un estándar de nivel empresarial (Enterprise-grade). 

El objetivo principal de esta guía es que este proyecto sea robusto, escalable, ininterrumpido ("vivo durante muchos años") y que justifique técnica y operativamente una valuación o venta en **$1,000,000 USD**.

---

## 1. Arquitectura de Producción (High-Level)

Para procesar miles de trámites diarios sin fallas, dividiremos el monolito local en microservicios gestionados (Serverless / PaaS).

| Componente | Plataforma de Producción | Razón del negocio |
|:---|:---|:---|
| **Frontend CRM (Twenty)** | **Vercel** | Edge Network global, CDN ultrarrápida, escalado infinito y costo cero de mantenimiento. |
| **Backend AI / Orquestador (FastAPI)** | **GCP Cloud Run** (o Railway) | Escalado automático a cero cuando no hay tráfico para ahorrar costos, sube a 1000s de instancias en picos (fin de mes). |
| **Base de Datos y Almacenamiento** | **Supabase** (Pro Tier) | PostgreSQL manejado, replicación automática, Storage S3 integrado y seguridad granular (RLS). |
| **Modelos Locales / OCR pesado** | **RunPod (Serverless)** | GPUs a demanda (A100/H100) para procesamiento de documentos sin tener que pagar hardware de miles de dólares ocioso. |
| **Automatización de Flujos** | **n8n / Vercel Functions** | Flujos de webhook escalables. |
| **Dominio y Seguridad** | **Cloudflare** / Vercel DNS | Protección DDoS capa 7, WAF y SSL dinámico. |

---

## 2. Fase 1: Creación y Preparación de Cuentas

Para un proyecto que se venderá a nivel corporativo, **nunca uses correos personales** (ej. `@gmail.com`). 
1. Adquiere el nombre de la empresa/dominio (ej. `insuracrm.com` o `promotoria-crm.com` - Ver Fase 4).
2. Crea un correo maestro de sistemas: `it@tudominio.com`.
3. Crea las cuentas en las siguientes plataformas con ese correo:
   - **GitHub** (Crea un *Organization Account*, no un usuario personal).
   - **Vercel** (Pro plan - $20/m, necesario o recomendable para límites altos).
   - **Supabase** (Pro plan - $25/m, para backups diarios automatizados de 7 a 30 días, esencial para la seguridad de la información).
   - **Google Cloud Platform (GCP)** (Crea un "GCP Project" e ingresa la tarjeta para activar la cuenta de facturación).
   - **RunPod** (Activa un fondo inicial de $50 USD para GPUs serverless).

---

## 3. Fase 2: Configuración de Base de Datos y Storage en Supabase

Supabase será el corazón transaccional donde convergen los flujos de inteligencia artificial y los eventos del CRM.

1. Crea tu proyecto en Supabase (Región AWS sugerida: `us-east-1` por latencia general o la más cercana a México ej. `us-west` / `us-east` en GCP/AWS si fuera Cloud Run el que se conecta).
2. Otorga la contraseña maestra pero **almacénala en un gestor de secretos** (1Password, Bitwarden).
3. En la sección *SQL Editor*, ejecuta las migraciones iniciales (`scripts/supabase/migrations/`). Empezando por la estructura principal, y finalmente las mejoras de modelo `006_data_model_enhancements.sql` (que soporta los ZIPs, análisis dinámicos, etc).
4. En *Storage*, crea un bucket llamado `policy-documents`.
   - Modifica las políticas (RLS) para que nadie pueda acceder públicamente (debe ser firmado el acceso vía el backend por confidencialidad de trámites GNP).
5. Recupera tu `SUPABASE_URL` y tu `SUPABASE_SERVICE_ROLE_KEY`. Estas irán al Backend.

---

## 4. Fase 3: Despliegues Individuales

### A. Frontend (React / Twenty CRM Modificado) -> VERCEL
1. En el dashboard de Vercel, da click en "Import Project" y enlaza tu organización de GitHub.
2. Selecciona el repositorio `twenty_olimpo`.
3. Vercel debe detectar los `.vercelignore` y el `vercel.json` previamente definidos en tu repo.
4. Variables de Entorno (Environment Variables) indispensables que debes configurar en Vercel de antemano:
   - `REACT_APP_SERVER_BASE_URL` (Debe apuntar al backend que configuraremos).
   - `REACT_APP_SUPABASE_URL` y `REACT_APP_SUPABASE_ANON_KEY`.
5. Deja que Vercel ejecute el build. Fallará si no tiene el backend.

### B. Backend API y Automatización (FastAPI / Twenty Server) -> GCP Cloud Run
Para alta escalabilidad sin manejar contenedores a mano:
1. Asegúrate de tener empaquetado tu servidor en un `Dockerfile` (Ya localizado en `packages/twenty-docker/...`).
2. Ve a GCP, habilita *Cloud Build*, *Container Registry / Artifact Registry*, y *Cloud Run*.
3. Construye el contenedor y súbelo a GCP. Como alternativa sencilla puedes usar **Railway**:
   - Enlaza el repositorio en Railway, selecciona la carpeta del backend.
   - Pega todas las variables del servidor (`DATABASE_URL` conectada al pgBouncer de Supabase).
   - Activa el HTTPS automático.

### C. Nodos de IA Pesada -> RunPod Serverless
1. En RunPod ve a "Serverless" -> "Templates".
2. Configura una imagen de Docker con tus modelos (ej. un contenedor de Python con pytesseract, OCR y bibliotecas de descifrado).
3. Establece una API Key de RunPod.
4. Esa URL y el API Key de RunPod debes insertarlas como variables de entorno (`RUNPOD_API_KEY`) en tu Backend de GCP/Railway.

---

## 5. Fase 4: Dominio, SSL y Branding

Parte del "valor" millonario es que esté bajo un esquema de dominio corporativo impecable, sin puertos en la URL.

1. **Adquiere tu dominio** (Ej. `crmpromotorialider.com`) en Namecheap, GoDaddy o Cloudflare Registrar.
2. **Conecta DNS a Cloudflare**: Esto sirve como Firewall escudo para evitar ataques o caídas (WAF mitigando pings falsos).
3. **Crea los Records CNAME**:
   - `app.tu-dominio.com` -> apunte a Vercel (`cname.vercel-dns.com`).
   - `api.tu-dominio.com` -> apunte a GCP Cloud Run o Railway.
4. El SSL lo generan en automático Vercel y Cloud Run/Railway, pero Cloudflare en modo "Full (Strict)" garantiza encriptación extremo a extremo (requerimiento OBLIGATORIO de la CNBV e ISO-27001 para datos financieros o pólizas).

---

## 6. Fase 5: GitHub y Flujo CI/CD

Un proyecto manual NO vale un millón de dólares. Un proyecto que se despliega automáticamente sí.

Debes configurar **GitHub Actions**:
Crea un archivo en `.github/workflows/production-deploy.yml`:

```yaml
name: Production Deploy Strategy
on:
  push:
    branches:
      - main
jobs:
  deploy-backend:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v3
        
      - name: Build & Deploy to GCP Cloud Run
        ... (Comandos para compilar tu Dockerfile o avisar a Railway/GCP por CLI que haga pull de la nueva imagen)
```
- Vercel ya se despliega de manera automática en el momento que haces push o un _merge_ a la rama que le hayas indicado (por ejemplo, `main`).

---

## 7. Fase 6: Estrategia de Ramas (Git Flow Empresarial)

Para mantener el proyecto vivo 10 años, un equipo requerirá trabajar sin romper la plataforma en vivo donde ingresan cientos de trámites de seguros. Debes respetar el siguiente modelo:

1. `main` (Rama de Producción Exclusiva): **NADIE** hace push directo a esta rama. Está bloqueada ("Branch Protection Rules" en Github). Solo acepta _Pull Requests_ revisados. El código aquí se despliega a la URL real que los clientes usan.
2. `staging` (Rama de Calidad/QA): Todo lo que se desarrolla entra aquí primero. Vercel te crea una URL temporal para `staging` y la base de datos debería ser distinta (un Supabase Development env) para hacer pruebas de QA.
3. `feature/nombre-de-la-mejora` (Ramas de Desarrollo Diario): Ej: `feature/descifrar-pdfs`, `feature/mejorar-dashboard`. Cuando terminas, haces un Pull Request (PR) hacia `staging`.
4. `hotfix/nombre-del-error` (Ramas de Emergencia): Solo si hay un error crítico en producción y hay que solucionarlo en 5 minutos. Se arregla y se hace PR directo a `main` y a `staging`.

---

## 8. Pitch para Inversionistas / Compradores ($1M USD Value Proposition)

A la hora de mostrar o vender la plataforma, céntrate en estos puntos que la arquitectura anterior resuelve:

1. **"Zero-Downtime Architecture":** La aplicación (Vercel + Cloud Run + Supabase) no tiene un solo "servidor físico" que se pueda dañar. Es 100% Serverless. Escala con la demanda.
2. **"Data Sovereignty & Encryption":** Aislamiento de datos confidenciales sobre seguros (RLS de Supabase), garantizando estándares casi bancarios.
3. **"AI Cost-Efficiency":** No tenemos servidores encendidos inútilmente ejecutando IA local; delegamos la abstracción a Runpod (hardware de IA a demanda) lo cual significa que tus gastos operativos (OPEX) son diminutos en comparación con el valor a entregar.
4. **"Predictable Updates (CI/CD)":** Contamos con repositorios estables bajo ramas protegidas, permitiendo al equipo de ingeniería introducir características sin caídas en producción.
5. **Base Extendible:** Al usar PostgreSQL, FastAPI y GraphQL, la infraestructura está lista para conectarse a legados, AS400, o corporativos como el mismo GNP en el futuro de manera nativa.

¡Con estos pasos, dejas a un lado un "hobby en Docker local" y tienes un proyecto nivel Silicon Valley, completamente automatizado, seguro y listo para ser valuado en el mercado corporativo!
