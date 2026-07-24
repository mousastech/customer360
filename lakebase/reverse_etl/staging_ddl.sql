-- T1 — Writable staging tables (Lakebase Postgres)
-- These live alongside the synced tables (customers_synced, transactions_synced,
-- products_synced) in capstone_db.public. The app writes notes / segment overrides
-- here as the app service principal; forward-ETL (T7) promotes them into gold.

-- Notes left by reps on a customer. processed=false until forward-ETL merges to gold.
CREATE TABLE IF NOT EXISTS customer_notes_staging (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id  TEXT        NOT NULL,
    note         TEXT        NOT NULL,
    author_email TEXT        NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed    BOOLEAN     NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS idx_notes_customer ON customer_notes_staging (customer_id);
CREATE INDEX IF NOT EXISTS idx_notes_unprocessed ON customer_notes_staging (processed) WHERE processed = false;

-- Segment overrides. One current override per customer (idempotent upsert on customer_id).
CREATE TABLE IF NOT EXISTS customer_segment_overrides_staging (
    customer_id   TEXT        PRIMARY KEY,
    segment_id    TEXT        NOT NULL,
    author_email  TEXT        NOT NULL,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed     BOOLEAN     NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS idx_overrides_unprocessed ON customer_segment_overrides_staging (processed) WHERE processed = false;

-- Append-only audit log for every write the app performs.
CREATE TABLE IF NOT EXISTS customer_audit_log (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_email  TEXT        NOT NULL,
    action       TEXT        NOT NULL,   -- e.g. 'add_note', 'override_segment'
    customer_id  TEXT        NOT NULL,
    detail       JSONB,
    request_id   TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_audit_customer ON customer_audit_log (customer_id);
