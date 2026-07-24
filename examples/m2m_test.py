"""T3a happy-path test: partner M2M call to the external API surface.

Flow:
  1. Mint an OAuth bearer via the SP client_credentials grant (see _token.py).
  2. Call GET {APP_URL}/api/external/customers/{id} with Authorization: Bearer <token>.
  3. Expect HTTP 200 + the CustomerDetail JSON.

The Apps proxy validates the bearer, strips Authorization, and forwards
X-Forwarded-Access-Token to the handler, which reads Delta gold via the SQL
warehouse as the partner SP (OBO) — never Lakebase, never the app SP.

Env vars:
    DATABRICKS_HOST, DATABRICKS_CLIENT_ID, DATABRICKS_CLIENT_SECRET  (see _token.py)
    APP_URL     deployed app base URL, e.g. https://customer360-xxxx.aws.databricksapps.com
    CUSTOMER_ID optional, defaults to C0000400
"""
from __future__ import annotations

import json
import os
import sys

import httpx

from _token import get_bearer


def main() -> int:
    app_url = os.environ["APP_URL"].rstrip("/")
    customer_id = os.environ.get("CUSTOMER_ID", "C0000400")

    bearer = get_bearer()
    url = f"{app_url}/api/external/customers/{customer_id}"
    print(f"GET {url}")

    resp = httpx.get(url, headers={"Authorization": f"Bearer {bearer}"}, timeout=60.0)
    print(f"HTTP {resp.status_code}")

    if resp.status_code != 200:
        print("FAILED — body:")
        print(resp.text[:2000])
        return 1

    body = resp.json()
    print(json.dumps(body, indent=2)[:2000])
    profile = body.get("profile", {})
    assert profile.get("customer_id") == customer_id, "customer_id mismatch"
    assert "transactions" in body, "missing transactions"
    print(f"\nOK — 200 + customer JSON for {customer_id} "
          f"({len(body['transactions'])} transactions)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
