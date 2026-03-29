#!/usr/bin/env node
/**
 * run-migrations.mjs
 * Aplica todas las migraciones de Supabase usando el cliente pg de Node.js.
 * No requiere psql instalado.
 *
 * Uso: node scripts/supabase/run-migrations.mjs
 */

import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const pg = require('pg');

const { Client } = pg;
const __dirname = dirname(fileURLToPath(import.meta.url));

// Leer .env
function loadEnv(envPath) {
  const lines = readFileSync(envPath, 'utf8').split('\n');
  const env = {};
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eqIdx = trimmed.indexOf('=');
    if (eqIdx === -1) continue;
    const key = trimmed.slice(0, eqIdx).trim();
    const val = trimmed.slice(eqIdx + 1).trim();
    env[key] = val;
  }
  return env;
}

const env = loadEnv(join(__dirname, '.env'));
const DB_URL = env['SUPABASE_DB_URL'];

if (!DB_URL || DB_URL.includes('[YOUR-PASSWORD]')) {
  console.error('❌ SUPABASE_DB_URL no configurado correctamente en .env');
  process.exit(1);
}

const MIGRATIONS_DIR = join(__dirname, 'migrations');

const files = readdirSync(MIGRATIONS_DIR)
  .filter(f => f.endsWith('.sql'))
  .sort();

const client = new Client({
  connectionString: DB_URL,
  ssl: { rejectUnauthorized: false }
});

async function main() {
  console.log('\n🚀 Olimpo Promotoría — Migraciones Supabase');
  console.log(`🔗 Conectando a Supabase...`);

  await client.connect();
  console.log('✅ Conexión establecida\n');

  for (const file of files) {
    const sql = readFileSync(join(MIGRATIONS_DIR, file), 'utf8');
    console.log(`▶ Aplicando ${file}...`);
    try {
      await client.query(sql);
      console.log(`✅ ${file} OK\n`);
    } catch (err) {
      console.error(`❌ Error en ${file}:`);
      console.error(`   ${err.message}`);
      await client.end();
      process.exit(1);
    }
  }

  console.log('🎉 Todas las migraciones aplicadas exitosamente.\n');

  // Verificar tablas creadas
  const { rows } = await client.query(`
    SELECT tablename
    FROM pg_tables
    WHERE schemaname = 'public'
      AND tablename IN (
        'incoming_emails', 'email_attachments', 'dedup_index',
        'ocr_results', 'ai_processing_log', 'contact_email_map'
      )
    ORDER BY tablename;
  `);

  console.log('📋 Tablas verificadas en Supabase:');
  rows.forEach(r => console.log(`   ✔ ${r.tablename}`));

  // Verificar buckets
  const { rows: buckets } = await client.query(`
    SELECT name FROM storage.buckets
    WHERE name IN ('incoming-raw', 'tramite-docs', 'ocr-output')
    ORDER BY name;
  `).catch(() => ({ rows: [] }));

  if (buckets.length > 0) {
    console.log('\n🪣 Buckets de Storage verificados:');
    buckets.forEach(b => console.log(`   ✔ ${b.name}`));
  }

  await client.end();
}

main().catch(err => {
  console.error('Error fatal:', err.message);
  process.exit(1);
});
