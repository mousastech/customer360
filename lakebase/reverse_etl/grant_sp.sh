#!/usr/bin/env bash
# T1 — one-time grant of Lakebase privileges to the app service principal.
#
# Fresh Postgres roles have NO privileges. The app SP logs in to Lakebase as a
# role named after its client_id (a UUID). Run this AFTER:
#   1. the app has been deployed (so its SP exists), and
#   2. the SP has connected to Lakebase at least once (so the role is created).
#
# Usage: ./grant_sp.sh <APP_SP_CLIENT_ID>
set -euo pipefail

SP_ROLE="${1:?Usage: grant_sp.sh <APP_SP_CLIENT_ID>}"
PROFILE="${DATABRICKS_PROFILE:-e2-demo-field-eng}"
INSTANCE="${PG_INSTANCE_NAME:-capstone-pg}"
PGHOST_VAL="${PGHOST:-ep-late-boat-d1i0mbwp.database.us-west-2.cloud.databricks.com}"
PGDATABASE_VAL="${PGDATABASE:-capstone_db}"

TOKEN=$(databricks database generate-database-credential \
  --json "{\"instance_names\":[\"${INSTANCE}\"]}" --profile "$PROFILE" -o json | jq -r '.token')
EMAIL=$(databricks current-user me --profile "$PROFILE" -o json | jq -r '.userName')

PGPASSWORD="$TOKEN" psql "host=$PGHOST_VAL port=5432 dbname=$PGDATABASE_VAL user=$EMAIL sslmode=require" <<SQL
-- Read on synced tables
GRANT USAGE ON SCHEMA public TO "$SP_ROLE";
GRANT SELECT ON customers_synced, transactions_synced, products_synced TO "$SP_ROLE";

-- Read + write on staging tables (+ audit)
GRANT SELECT, INSERT, UPDATE ON customer_notes_staging, customer_segment_overrides_staging TO "$SP_ROLE";
GRANT SELECT, INSERT ON customer_audit_log TO "$SP_ROLE";

-- Identity sequences behind BIGINT GENERATED ALWAYS columns
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "$SP_ROLE";

-- Future synced tables (re-sync recreates them) inherit SELECT for the SP
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO "$SP_ROLE";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO "$SP_ROLE";
SQL

echo "Granted Lakebase privileges to SP role: $SP_ROLE"
