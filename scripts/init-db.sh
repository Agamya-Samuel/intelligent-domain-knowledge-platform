#!/bin/bash
# init-db.sh — runs once on first Postgres container start.
# Creates the separate `langfuse` database used by the Langfuse service.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE langfuse;
EOSQL

echo "Created 'langfuse' database alongside '$POSTGRES_DB'."
