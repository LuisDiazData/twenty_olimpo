"""
apply_supabase_migrations.py
============================
Aplica las migraciones de Supabase pendientes que no se pueden ejecutar via REST.
Usa psql en el container de Docker para conectar al Supabase cloud.

Tablas a crear:
  - historial_estatus    (012_historial_estatus.sql)
  - notas_interacciones  (017_notas_interacciones.sql)
  - agent_performance_monthly (018_agent_performance_monthly.sql)
  - kpi_snapshots_cache  (015_kpi_snapshots_cache.sql)

Uso:
  python3 scripts/apply_supabase_migrations.py <DB_PASSWORD>

  La contraseña está en: Supabase Dashboard → Settings → Database → Database password
"""

import subprocess
import sys
import os
from pathlib import Path

PROJECT_REF = os.getenv("SUPABASE_PROJECT_REF", "")
DB_HOST = os.getenv("SUPABASE_DB_HOST", "aws-0-us-east-1.pooler.supabase.com")
DB_PORT = os.getenv("SUPABASE_DB_PORT", "5432")
DB_USER = os.getenv("SUPABASE_DB_USER", f"postgres.{PROJECT_REF}")
DB_NAME = os.getenv("SUPABASE_DB_NAME", "postgres")

MIGRATIONS_DIR = Path(__file__).parent / "supabase" / "migrations"
DOCKER_CONTAINER = "twenty-db-1"

PENDING_MIGRATIONS = [
    "012_historial_estatus.sql",
    "015_kpi_snapshots_cache.sql",
    "017_notas_interacciones.sql",
    "018_agent_performance_monthly.sql",
]


def run_migration(password: str, sql_file: Path) -> bool:
    """Runs a SQL file via psql inside the Docker container."""
    print(f"\n  Applying: {sql_file.name}")

    # Read the SQL file
    sql = sql_file.read_text()

    cmd = [
        "docker", "exec", "-i", DOCKER_CONTAINER,
        "psql",
        f"postgresql://{DB_USER}:{password}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
        "-c", sql,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode == 0:
        print(f"  ✓ {sql_file.name} aplicado")
        return True
    else:
        print(f"  ✗ ERROR en {sql_file.name}:")
        print(f"    {result.stderr[:500]}")
        return False


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("ERROR: Proporciona la contraseña de Supabase como argumento.")
        print("  python3 scripts/apply_supabase_migrations.py <TU_PASSWORD>")
        sys.exit(1)

    password = sys.argv[1]

    print("=" * 60)
    print("  Aplicando migraciones Supabase pendientes")
    print(f"  Host: {DB_HOST}")
    print(f"  User: {DB_USER}")
    print("=" * 60)

    success_count = 0
    for migration_name in PENDING_MIGRATIONS:
        migration_file = MIGRATIONS_DIR / migration_name
        if not migration_file.exists():
            print(f"\n  SKIP: {migration_name} no encontrado")
            continue
        if run_migration(password, migration_file):
            success_count += 1

    print(f"\n{'=' * 60}")
    print(f"  {success_count}/{len(PENDING_MIGRATIONS)} migraciones aplicadas")
    print(f"{'=' * 60}")

    if success_count == len(PENDING_MIGRATIONS):
        print("\n  Ahora puedes volver a correr el seed para llenar las tablas:")
        print("  python3 scripts/seed_datos_prueba.py")


if __name__ == "__main__":
    main()
