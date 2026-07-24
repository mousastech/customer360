# Deploy — git-source app via DABs (T8)

The app must deploy as a **git-source app** (workspace-folder uploads are not
accepted). Databricks pulls source from your GitHub fork on each `bundle run`.

## 0. One-time: fork + push

```bash
# Fork jnshubham-db/gdc-apps-lakebase-capstone into your own account, then:
cd ~/capstone-app
git init && git add -A && git commit -m "Customer 360 capstone"
git remote add origin https://github.com/<you>/gdc-apps-lakebase-capstone.git
git push -u origin main
```

Then set the repo URL in `databricks.yml` (`variables.git_repo_url.default`) or
pass `--var git_repo_url=https://github.com/<you>/gdc-apps-lakebase-capstone`.

## 1. Validate + deploy + run

```bash
P=e2-demo-field-eng
databricks bundle validate --target prod --profile $P
databricks bundle deploy   --target prod --profile $P
databricks bundle run customer360 --target prod --profile $P
```

`bundle run` is what makes Databricks pull the latest commit from the declared
git ref and restart the app (it is NOT a job trigger). Re-run it after every
`git push` + `bundle deploy`.

## 2. Bind the GitHub credential to the app's service principal

The workspace pulls source **as the app SP**, not as you. Register a git
credential bound to the SP id (single call, run as your normal profile):

```bash
# after the first deploy, get the app SP id
APP_SP_ID=$(databricks apps get customer360 --profile $P -o json | jq -r '.service_principal_id')

databricks git-credentials create --json "{
  \"git_provider\": \"gitHub\",
  \"git_email\": \"<bot-email>\",
  \"personal_access_token\": \"<github_pat>\",
  \"principal_id\": ${APP_SP_ID},
  \"name\": \"GitHub credentials for app SP\"
}" --profile $P

# re-run so the source pull succeeds
databricks bundle run customer360 --target prod --profile $P
```

If you delete + recreate the app, the SP id changes — re-register the credential.

## 3. Grant the app SP Lakebase privileges (T1 finish)

Once the app SP has connected to Lakebase at least once:

```bash
APP_SP_CLIENT_ID=$(databricks apps get customer360 --profile $P -o json | jq -r '.service_principal_client_id')
./lakebase/reverse_etl/grant_sp.sh "$APP_SP_CLIENT_ID"
```

## 4. Workspace toggles (one-time, admin)

- **OBO preview:** Settings → Apps → *User authorization (preview)* = ON.
  Without it, `user_api_scopes` silently drop and `X-Forwarded-Access-Token`
  is never injected.

  > **Confirmed blocker on `e2-demo-field-eng` (2026-07-24):** the deployed app
  > has `user_api_scopes: [sql, dashboards.genie]` configured, but
  > `effective_user_api_scopes` shows only `[iam.access-control:read,
  > iam.current-user:read]` — the preview toggle is OFF and this account
  > (`grupo_1_admin`, not the workspace `admins` group) can't flip it
  > (`workspace-conf` → Forbidden). Effect: **Lakebase reads via the app SP work
  > (customer list + detail render live), and SP-based warehouse queries work
  > (`/api/segments` → 200 after granting the SP `USE CATALOG mozuca`), but the
  > OBO-based metrics + Genie endpoints return 401 "OAuth token does not have
  > required scopes: sql"** until a workspace admin enables the toggle. No code
  > change fixes this — it is purely the workspace setting.
- **Dashboard embed allowlist:** Settings → Security → External Access →
  *Embed Dashboard* → add the app host
  (`customer360-<id>.aws.databricksapps.com`), else the iframe is blocked by
  `X-Frame-Options`.
- **First load** prompts each user to Authorize the `sql` + `dashboards.genie`
  scopes once.

## Build hygiene (already handled)

- No `app/package.json` at the app root (only `app/frontend/package.json`), so
  the runtime won't try `npm build` at the wrong level.
- `app/backend/static/` (built React bundle) is committed, so the runtime
  command is a plain `uvicorn backend.main:app` with no build step.
- Rebuild before committing when frontend changes: `cd app/frontend && bun run build`.
