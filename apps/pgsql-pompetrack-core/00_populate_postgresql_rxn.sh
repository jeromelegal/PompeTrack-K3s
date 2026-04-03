#!/bin/sh
set -eu

LOG_FILE="/tmp/rxnorm_init.log"
rm -f "$LOG_FILE"
touch "$LOG_FILE"

echo "----------------------------------------" >> "$LOG_FILE" 2>&1
echo "Starting RxNorm PostgreSQL init ... $(date)" >> "$LOG_FILE" 2>&1
echo "----------------------------------------" >> "$LOG_FILE" 2>&1
echo "POSTGRES_DB=${POSTGRES_DB:-}" >> "$LOG_FILE" 2>&1
echo "POSTGRES_USER=${POSTGRES_USER:-}" >> "$LOG_FILE" 2>&1

export PGPASSWORD="${POSTGRES_PASSWORD:-}"

run_sql() {
  file="$1"
  echo "Running $file ... $(date)" >> "$LOG_FILE" 2>&1
  psql \
    -v ON_ERROR_STOP=1 \
    --username "${POSTGRES_USER}" \
    --dbname "${POSTGRES_DB}" \
    --file "$file" >> "$LOG_FILE" 2>&1
}

run_sql /docker-entrypoint-initdb.d/01_Table_scripts_postgresql_rxn.sql
run_sql /docker-entrypoint-initdb.d/02_Load_scripts_postgresql_rxn_unix.sql
run_sql /docker-entrypoint-initdb.d/03_Indexes_postgresql_rxn.sql

echo "Completed without errors." >> "$LOG_FILE" 2>&1
echo "Finished ... $(date)" >> "$LOG_FILE" 2>&1
echo "----------------------------------------" >> "$LOG_FILE" 2>&1