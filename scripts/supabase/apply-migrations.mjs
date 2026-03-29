#!/usr/bin/env node
/**
 * apply-migrations.mjs
 * Aplica las migraciones de Supabase en orden.
 *
 * Uso:
 *   node scripts/supabase/apply-migrations.mjs
 *
 * Requiere:
 *   - SUPABASE_DB_URL en scripts/supabase/.env (con password real)
 *   - psql instalado en el sistema, O conexión vía Supabase REST
 *
 * Alternativa sin psql: pega cada archivo en Supabase Dashboard > SQL Editor
 */

import { execSync } from 'node:child_process';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';
import { config } from 'node:process';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ENV_PATH = join(__dirname, '.env');

// Leer .env manualmente (sin dependencias externas)
function loadEnv(envPath) {
  const lines = readFileSync(envPath, 'utf8').split('\n');
  const env = {};
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const [key, ...rest] = trimmed.split('=');
    env[key.trim()] = rest.join('=').trim();
  }
  return env;
}

const env = loadEnv(ENV_PATH);
const DB_URL = env['SUPABASE_DB_URL'];

if (!DB_URL || DB_URL.includes('[YOUR-PASSWORD]')) {
  console.error('❌ Error: SUPABASE_DB_URL no configurado o tiene [YOUR-PASSWORD] sin reemplazar.');
  console.error('   Edita scripts/supabase/.env y pon la contraseña real de tu proyecto Supabase.');
  console.error('   La encuentras en: Supabase Dashboard > Settings > Database > Connection string');
  process.exit(1);
}

const MIGRATIONS_DIR = join(__dirname, 'migrations');

function getMigrationFiles() {
  return readdirSync(MIGRATIONS_DIR)
    .filter(f => f.endsWith('.sql'))
    .sort();  // orden alfabético = orden numérico (001_, 002_, ...)
}

function applyMigration(filename) {
  const fullPath = join(MIGRATIONS_DIR, filename);
  const sql = readFileSync(fullPath, 'utf8');

  console.log(`\n▶ Aplicando ${filename}...`);

  try {
    execSync(`psql "${DB_URL}" -f "${fullPath}"`, {
      stdio: 'inherit',
      env: { ...process.env, PGPASSWORD: DB_URL.match(/:([^:@]+)@/)?.[1] ?? '' }
    });
    console.log(`✅ ${filename} aplicado correctamente.`);
  } catch (err) {
    console.error(`❌ Error en ${filename}:`);
    console.error(err.message);
    process.exit(1);
  }
}

// -------------------------------------------------------
// Verificar que psql esté disponible
// -------------------------------------------------------
try {
  execSync('psql --version', { stdio: 'pipe' });
} catch {
  console.error('❌ psql no está instalado o no está en el PATH.');
  console.error('');
  console.error('Opciones:');
  console.error('  1. Instala PostgreSQL client: https://www.postgresql.org/download/');
  console.error('  2. Aplica las migraciones manualmente en:');
  console.error('     Supabase Dashboard > SQL Editor');
  console.error('     Archivos en: scripts/supabase/migrations/');
  process.exit(1);
}

// -------------------------------------------------------
// Aplicar migraciones
// -------------------------------------------------------
const files = getMigrationFiles();
console.log(`\n🚀 Olimpo Promotoría — Migraciones Supabase`);
console.log(`📁 ${files.length} archivos encontrados en migrations/`);
console.log(`🔗 Conectando a: ${DB_URL.replace(/:([^:@]+)@/, ':****@')}`);

for (const file of files) {
  applyMigration(file);
}

console.log('\n✅ Todas las migraciones aplicadas exitosamente.');
console.log('\nPróximos pasos:');
console.log('  1. Verifica las tablas en Supabase Dashboard > Table Editor');
console.log('  2. Verifica los buckets en Supabase Dashboard > Storage');
console.log('  3. Habilita pg_cron en Dashboard > Database > Extensions');
console.log('  4. Obtén tu service_role key en Dashboard > Settings > API');
console.log('     y agrégala a scripts/supabase/.env como SUPABASE_SERVICE_ROLE_KEY');
