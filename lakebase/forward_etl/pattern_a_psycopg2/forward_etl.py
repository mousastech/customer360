# Databricks notebook source
# MAGIC %md
# MAGIC # Forward ETL — Pattern A (psycopg + MERGE INTO Delta)
# MAGIC
# MAGIC Pull unprocessed rows from Lakebase staging, MERGE INTO gold, then mark
# MAGIC them processed — all as the app service principal. Idempotent: re-running
# MAGIC with no new staging rows is a no-op (the `processed = false` filter).
# MAGIC
# MAGIC Runs as a Databricks Job (see resources/jobs.yml). The Reports page
# MAGIC triggers it via the Jobs API.

# COMMAND ----------

import json

import psycopg
from psycopg.rows import dict_row
from pyspark.sql import functions as F
from databricks.sdk import WorkspaceClient

# COMMAND ----------

dbutils.widgets.text("catalog", "mozuca")
dbutils.widgets.text("pg_instance_name", "capstone-pg")
dbutils.widgets.text("pg_host", "ep-late-boat-d1i0mbwp.database.us-west-2.cloud.databricks.com")
dbutils.widgets.text("pg_database", "capstone_db")

CATALOG = dbutils.widgets.get("catalog")
GOLD = f"{CATALOG}.gold"
PG_INSTANCE = dbutils.widgets.get("pg_instance_name")
PG_HOST = dbutils.widgets.get("pg_host")
PG_DATABASE = dbutils.widgets.get("pg_database")

# COMMAND ----------

# Connect to Lakebase as the running identity (the job's SP). The credential is
# minted through the same generate_database_credential path the app uses.
w = WorkspaceClient()
cred = w.database.generate_database_credential(instance_names=[PG_INSTANCE])
me = w.current_user.me().user_name

conn = psycopg.connect(
    host=PG_HOST,
    port=5432,
    dbname=PG_DATABASE,
    user=me,
    password=cred.token,
    sslmode="require",
    row_factory=dict_row,
)
print(f"connected to Lakebase {PG_HOST}/{PG_DATABASE} as {me}")

# COMMAND ----------

# MAGIC %md ## 1. Notes: staging → gold.customer_notes

# COMMAND ----------

with conn.cursor() as cur:
    cur.execute(
        "SELECT id, customer_id, note, author_email, created_at "
        "FROM customer_notes_staging WHERE processed = false ORDER BY id"
    )
    note_rows = cur.fetchall()

print(f"{len(note_rows)} unprocessed notes")

if note_rows:
    notes_df = (
        spark.createDataFrame(note_rows)
        .withColumn("merged_at", F.current_timestamp())
    )
    notes_df.createOrReplaceTempView("notes_src")
    spark.sql(f"""
        MERGE INTO {GOLD}.customer_notes AS t
        USING notes_src AS s
        ON t.id = s.id
        WHEN NOT MATCHED THEN INSERT
          (id, customer_id, note, author_email, created_at, merged_at)
          VALUES (s.id, s.customer_id, s.note, s.author_email, s.created_at, s.merged_at)
    """)
    merged_ids = [r["id"] for r in note_rows]
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE customer_notes_staging SET processed = true WHERE id = ANY(%s)",
            [merged_ids],
        )
    conn.commit()
    print(f"merged + marked {len(merged_ids)} notes processed")

# COMMAND ----------

# MAGIC %md ## 2. Segment overrides: staging → gold.customer_segment_overrides
# MAGIC MERGE on customer_id (upsert) so re-runs and re-overrides stay idempotent.

# COMMAND ----------

with conn.cursor() as cur:
    cur.execute(
        "SELECT customer_id, segment_id, author_email, updated_at "
        "FROM customer_segment_overrides_staging WHERE processed = false ORDER BY customer_id"
    )
    ovr_rows = cur.fetchall()

print(f"{len(ovr_rows)} unprocessed overrides")

if ovr_rows:
    ovr_df = (
        spark.createDataFrame(ovr_rows)
        .withColumn("merged_at", F.current_timestamp())
    )
    ovr_df.createOrReplaceTempView("ovr_src")
    spark.sql(f"""
        MERGE INTO {GOLD}.customer_segment_overrides AS t
        USING ovr_src AS s
        ON t.customer_id = s.customer_id
        WHEN MATCHED THEN UPDATE SET
          t.segment_id = s.segment_id, t.author_email = s.author_email,
          t.updated_at = s.updated_at, t.merged_at = s.merged_at
        WHEN NOT MATCHED THEN INSERT
          (customer_id, segment_id, author_email, updated_at, merged_at)
          VALUES (s.customer_id, s.segment_id, s.author_email, s.updated_at, s.merged_at)
    """)
    ovr_ids = [r["customer_id"] for r in ovr_rows]
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE customer_segment_overrides_staging SET processed = true "
            "WHERE customer_id = ANY(%s)",
            [ovr_ids],
        )
    conn.commit()
    print(f"merged + marked {len(ovr_ids)} overrides processed")

# COMMAND ----------

conn.close()
result = {"notes_merged": len(note_rows), "overrides_merged": len(ovr_rows)}
print(json.dumps(result))
dbutils.notebook.exit(json.dumps(result))
