# External API — M2M test (T3a)

`GET /api/external/customers/{id}` returns the same `CustomerDetail` shape as the
in-app detail endpoint, but reads **Delta gold via the SQL warehouse** using the
caller's bearer (OBO) — never Lakebase, never the app SP.

## Deploy-time setup (run once, after the app is deployed)

1. **Pick the SP.** Use the app's own SP or a dedicated "partner integration" SP.
2. **Mint an OAuth client_secret** for the SP:
   ```bash
   databricks service-principal-secrets-proxy create <SP_ID> --profile e2-demo-field-eng
   ```
   Save `client_id` + `client_secret`.
3. **Grant CAN_USE on the app** to the SP (App → Permissions → Add → Service
   principal → CAN_USE). Without it the proxy returns 401.
4. **Grant warehouse + gold reads** to the SP: `CAN_USE` on the warehouse,
   `USE CATALOG mozuca`, `USE SCHEMA mozuca.gold`, `SELECT` on
   `mozuca.gold.customers` and `mozuca.gold.transactions`.

## Run the test

```bash
export DATABRICKS_HOST=https://e2-demo-field-eng.cloud.databricks.com
export DATABRICKS_CLIENT_ID=<sp_client_id>
export DATABRICKS_CLIENT_SECRET=<sp_client_secret>
export APP_URL=https://customer360-xxxx.aws.databricksapps.com
uv run --with httpx --with databricks-sdk python examples/m2m_test.py
```

Expect `HTTP 200` + the customer JSON. Confirm in the SQL audit log that the
statement is attributed to the **partner SP**, not the deploying user.
