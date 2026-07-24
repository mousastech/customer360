"""Shared helper: run the SDK's M2M (OAuth client_credentials) flow, return a bearer.

A partner authenticates as a service principal. The SDK exchanges the SP's
client_id / client_secret at ``<host>/oidc/v1/token`` for a short-lived OAuth
access token. That access_token — NOT the client_secret — is what goes in the
Authorization header to the Apps proxy.

Env vars:
    DATABRICKS_HOST            e.g. https://e2-demo-field-eng.cloud.databricks.com
    DATABRICKS_CLIENT_ID       the partner SP's client_id
    DATABRICKS_CLIENT_SECRET   the partner SP's OAuth client_secret
"""
from __future__ import annotations

import os

from databricks.sdk.core import Config, oauth_service_principal


def get_bearer() -> str:
    host = os.environ["DATABRICKS_HOST"]
    client_id = os.environ["DATABRICKS_CLIENT_ID"]
    client_secret = os.environ["DATABRICKS_CLIENT_SECRET"]

    cfg = Config(host=host, client_id=client_id, client_secret=client_secret)
    credentials_provider = oauth_service_principal(cfg)
    if credentials_provider is None:
        raise RuntimeError("Could not build M2M credentials provider — check host/client_id/secret")

    headers = credentials_provider()  # {"Authorization": "Bearer <access_token>"}
    auth = headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise RuntimeError(f"Unexpected auth header shape: {auth[:24]}…")
    return auth.removeprefix("Bearer ")


if __name__ == "__main__":
    token = get_bearer()
    print(f"Minted OAuth access token (len={len(token)}): {token[:16]}…")
