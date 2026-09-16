#!/usr/bin/env bash
set -euo pipefail

# Loads environment variables from .env if present
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

DB_NAME=llm_sql_analyst
DB_USER=llm_sql_user
DB_PASS=llm_sql_pass

echo "==> Creating role and database (safe to re-run)..."
sudo -u postgres psql -v ON_ERROR_STOP=0 <<-SQL
  DO \$\$
  BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${DB_USER}') THEN
      CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASS}';
    END IF;
  END
  \$\$;
SQL

sudo -u postgres createdb -O "${DB_USER}" "${DB_NAME}" 2>/dev/null || echo "Database ${DB_NAME} already exists, skipping."

echo "==> Applying schema..."
PGPASSWORD="${DB_PASS}" psql -h localhost -U "${DB_USER}" -d "${DB_NAME}" -f data/init_db.sql

echo "==> Done. Now run: python -m data.generate_seed_data"
