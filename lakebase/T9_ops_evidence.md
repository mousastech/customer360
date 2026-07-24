# T9 — Lakebase Ops Evidence

Executed live against Provisioned instance `capstone-pg` (`capstone_db`) on 2026-07-24.

## T9a — Branch + PITR

**Branch creation.** Created child instance `capstone-pg-branch` from
`capstone-pg` (`parent_instance_ref.name = capstone-pg`). The branch inherited
the parent's data at branch time:

| step | rows in `customer_notes_staging` |
|---|---|
| seeded on parent | 5 |
| on the branch (inherited) | 5 |
| **DELETE FROM customer_notes_staging on branch (destructive)** | **0** |
| parent (unaffected by branch delete) | 5 |

**PITR restore.** Captured restore target `2026-07-24T23:13:31Z` (after the seed,
before the delete), then ran `DELETE FROM customer_notes_staging` on the **parent**
(→ 0 rows). Created `capstone-pg-restored` from
`parent_instance_ref = { name: capstone-pg, branch_time: 2026-07-24T23:13:31Z }`.

| instance | rows after restore |
|---|---|
| `capstone-pg` (parent, post-delete) | 0 |
| **`capstone-pg-restored` (PITR @ pre-delete ts)** | **5** ✅ recovered |

> Provisioned tier allows only 1 child per parent, so the branch was deleted
> before creating the PITR instance. Both operations use the same
> `create-database-instance` + `parent_instance_ref` API; `branch_time` is what
> makes it a point-in-time restore vs a live branch.

## T9b — Query insights (index impact)

Query: `SELECT * FROM customer_audit_log WHERE actor_email = '…'` over 50,001 rows,
run 100× (varying the email). Latency from `EXPLAIN (ANALYZE)` Execution Time.

| | plan | mean (ms) | **p95 (ms)** | max (ms) |
|---|---|---|---|---|
| **before** (no index on `actor_email`) | Seq Scan (49,901 rows filtered) | 2.919 | **3.469** | 9.173 |
| **after** `CREATE INDEX idx_audit_actor_email ON customer_audit_log (actor_email)` | Bitmap Index Scan | 0.212 | **0.390** | 2.252 |

**Result: p95 latency ~8.9× lower (3.469 → 0.390 ms); mean ~14× lower.** The
planner switched from a full Seq Scan to a Bitmap Index Scan on the new index.

`pg_stat_statements` was enabled (`CREATE EXTENSION`) and reset before the run to
observe per-statement aggregates alongside the EXPLAIN-based measurement.
