# Customer 360 — Databricks Apps + Lakebase Capstone

A "customer success" web app for **Acme Retail** (10k synthetic customers) built on
Databricks Apps with a Lakebase (Provisioned) backing store, SQL warehouse
aggregates, an embedded AI/BI dashboard, a Genie chat overlay, and a forward-ETL
job. React + Vite + TanStack Query frontend, FastAPI + psycopg backend.

## Provisioned environment (installer)

| Resource | Value |
|---|---|
| Workspace | `e2-demo-field-eng` |
| Gold catalog / schema | `mozuca.gold` (customers, transactions, products, customer_segments, support_tickets) |
| Lakebase (Provisioned) | `capstone-pg` / `capstone_db`, UC catalog `capstone_lakebase` |
| SQL warehouse | `8baced1ff014912d` (serverless) |
| AI/BI dashboard | `01f187aa3ef218caaf91091d67fdb124` |
| Genie space | `01f187ad0b031f7997246b22d4337fff` |

## Architecture

```
React (Vite, TanStack Query)  ──/api──▶  FastAPI
                                          ├─ Lakebase synced reads   (app SP, psycopg pool)     → customers/transactions/products
                                          ├─ Lakebase staging writes (app SP, transactional)    → notes / segment overrides + audit
                                          ├─ SQL warehouse           (OBO, caller bearer)        → cross-table metrics + external API
                                          ├─ Genie Conversation API  (OBO)                       → floating chat
                                          └─ Jobs API                (app SP)                     → forward-ETL trigger
```

- **Reads**: Lakebase synced tables (`customers_synced`, `transactions_synced`,
  `products_synced`) via the app service principal — sub-10ms in-region.
- **Metrics + external API**: cross-table aggregates against Delta gold via the
  SQL warehouse using the **calling user's / partner SP's OBO bearer**, so
  warehouse RLS + audit reflect the real identity.
- **Writes**: notes + segment overrides land in Lakebase staging tables,
  transactionally paired with an append to `customer_audit_log`.
- **Forward-ETL** (Pattern A): a notebook job reads unprocessed staging rows,
  `MERGE INTO` gold, marks them processed — idempotent by the `processed=false`
  filter. Triggered from the Reports page via the Jobs API.

## Layout

```
app/
  app.yaml                     # T6: env + OBO scopes + resource bindings
  pyproject.toml               # backend deps (uv)
  backend/
    main.py                    # FastAPI app, middleware, /api/config, static SPA
    config.py auth.py db.py     # settings, OBO/SP clients, Lakebase pool
    warehouse.py cache.py models.py
    routers/ customers.py genie.py external.py jobs.py
    static/                    # committed built React bundle (no runtime build step)
  frontend/                    # React + Vite + TS (package.json lives HERE, not at app root)
    src/ pages/ components/ api/
lakebase/
  reverse_etl/ staging_ddl.sql grant_sp.sh      # T1
  forward_etl/pattern_a_psycopg2/forward_etl.py # T7
  T9_ops_evidence.md                            # T9 branch/PITR + query-insights results
resources/ app.yml jobs.yml lakebase.yml        # T8 DABs
examples/ _token.py m2m_test.py README.md       # T3a M2M test
databricks.yml                                  # T8 bundle root
DEPLOY.md                                       # git-source deploy runbook
```

## Local dev

```bash
# backend
cd app && uv run uvicorn backend.main:app --reload --port 8000   # DATABRICKS_PROFILE from .env
# frontend (proxies /api → :8000)
cd app/frontend && bun run dev        # http://localhost:5173
# production build (commit the output)
cd app/frontend && bun run build      # → app/backend/static/
```

## Deploy

See **DEPLOY.md** — git-source app via `databricks bundle validate/deploy/run`,
SP-bound GitHub credential, and the one-time workspace toggles (OBO preview,
dashboard-embed allowlist).

## Task coverage

| Task | Status | Evidence |
|---|---|---|
| T1 synced + staging tables | ✅ live | 3 synced tables ONLINE (10k/100.6k/200 rows), 3 staging tables created |
| T2 OBO + SP auth | ✅ live | `/api/me`, SP Lakebase `SELECT 1`, OBO warehouse metrics |
| T3 APIs + React UI | ✅ live | list/detail/metrics/notes/segment verified in-browser; server-side pagination + audit + idempotent override |
| T3a external M2M | ✅ code + local | handler reads gold via warehouse; `examples/m2m_test.py` for deployed run |
| T4 dashboard embed | ✅ | `/api/config` + iframe `embed/dashboardsv3/{id}` |
| T5 Genie chat | ✅ live | floating overlay, poll loop, SQL + result preview verified |
| T6 app.yaml | ✅ | env + `user_authorization` scopes `[sql, dashboards.genie]` + resource bindings |
| T7 forward-ETL | ✅ code | Pattern A notebook + jobs.py + Reports.tsx; runs after deploy |
| T8 git-source DABs | ✅ validated | `bundle validate --target prod` OK; deploy/run + git credential in DEPLOY.md |
| T9 branch/PITR + query insights | ✅ live | see `lakebase/T9_ops_evidence.md` |

> Deploy-later items (per build-now decision): actual `bundle deploy/run`, the
> SP-bound GitHub credential, the SP-grant step (`grant_sp.sh`), and the M2M
> end-to-end run — all documented in DEPLOY.md, ready to execute once the repo
> + PAT are in place.

## Reflection

**Sync-mode choices.** `customers_synced` and `transactions_synced` are
**CONTINUOUS** — the app's core reads must reflect upstream gold within seconds
(a rep viewing an account right after an upstream refresh should see current
data). `products_synced` is **TRIGGERED** (hourly): the 200-row catalog is
slow-changing, so a continuously-running pipeline for near-static data is pure
waste — an hourly trigger keeps it fresh enough without holding a pipeline open.

**Optimizations implemented.**
- *Pagination*: server-side always, `{items,total,page,page_size}`, default 25 /
  hard cap 100 (422 above), ordered by `lifetime_value DESC, customer_id`. Added
  composite index `(segment_id, lifetime_value DESC)` on the synced table.
- *Caching*: server-side TTLCache (5 min) on `/api/config` + segments;
  TanStack Query per-key `staleTime` (list 10s, detail 30s, metrics 60s, config
  5m); `invalidateQueries` after writes; `Cache-Control: private, max-age=10`
  on idempotent GETs.
- *Connection pooling*: `psycopg_pool` (2–10) with a custom `OAuthConnection`
  that mints a fresh Lakebase token per checkout and `max_lifetime=2700` to
  recycle before the 1-h token expiry — no background refresh task.
- *React*: route-level `React.lazy` + `<Suspense>` code-splitting (Customers,
  Detail, Dashboard, Reports are separate chunks); memoized list rows; 250ms
  debounced filter inputs; parallel per-tab fetches via `useQueries`.
- *API hygiene*: `GZipMiddleware`, Pydantic response models, per-request
  `X-Request-Id`, structured JSON logging, slow-query (>500ms) WARNING logging,
  warehouse statement timeouts.
- *Lakebase*: index `idx_audit_actor_email` (T9b — p95 3.47→0.39ms).

**What I'd add next.** Keyset (cursor) pagination for the list once past a few
thousand rows to avoid OFFSET cost; `fastapi-cache` with a shared backend if the
app scales to multiple instances; a read-replica endpoint for the heavy metrics
reads; and Pattern B (Lakehouse Sync CDC) as an alternative forward-ETL path to
get SCD2 history for free.

> **Note on local latency**: server-side list timing measured from a laptop is
> ~800ms — dominated by cross-region round-trips to the Lakebase proxy in
> us-west-2, not query time (EXPLAIN shows single-digit-ms execution). Deployed
> in-region as a Databricks App, this collapses to the sub-200ms target.
