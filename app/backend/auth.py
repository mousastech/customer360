"""Authentication: OBO (calling user) and service-principal WorkspaceClients.

Two identities are in play:

* **OBO** — the Databricks Apps proxy injects ``X-Forwarded-Access-Token`` carrying
  the *calling user's* identity. Used for SQL warehouse + Genie so workspace RLS and
  audit reflect the real user.
* **SP** — the app's own service principal (credentials provided by the runtime).
  Used for all Lakebase access and the forward-ETL job trigger.

Note: Lakebase does NOT support OBO scopes, so there is deliberately no
``lakebase_obo()``. All DB access runs as the SP; the calling user's email is read
from ``X-Forwarded-Email`` and recorded in the audit log.
"""
from __future__ import annotations

from functools import lru_cache

from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config
from fastapi import HTTPException, Request

from .config import IS_DATABRICKS_APP, get_settings

_ACCESS_TOKEN_HEADER = "X-Forwarded-Access-Token"
_EMAIL_HEADER = "X-Forwarded-Email"


def obo_client(request: Request) -> WorkspaceClient:
    """Build a WorkspaceClient acting as the calling user (OBO).

    Reads ``X-Forwarded-Access-Token`` from the request. Used for SQL warehouse
    and Genie calls so downstream identity is the user, not the SP.
    """
    token = request.headers.get(_ACCESS_TOKEN_HEADER)
    if not token:
        if not IS_DATABRICKS_APP:
            # Local dev fallback: use the CLI profile identity so devs can iterate.
            return _local_client()
        raise HTTPException(
            status_code=401,
            detail=(
                "Missing X-Forwarded-Access-Token. Ensure the workspace OBO preview "
                "toggle is on and the user has authorized the app's scopes."
            ),
        )
    # Force PAT auth and ignore ambient SP env creds (DATABRICKS_CLIENT_ID/SECRET),
    # else the SDK errors "more than one authorization method configured: oauth and pat".
    cfg = Config(host=get_settings().host, token=token, auth_type="pat")
    return WorkspaceClient(config=cfg)


def caller_email(request: Request) -> str:
    """Calling user's email from the proxy header (for the audit log)."""
    email = request.headers.get(_EMAIL_HEADER)
    if email:
        return email
    if not IS_DATABRICKS_APP:
        try:
            return _local_client().current_user.me().user_name or "local-dev"
        except Exception:  # pragma: no cover - offline dev
            return "local-dev"
    return "unknown"


@lru_cache(maxsize=1)
def sp_client() -> WorkspaceClient:
    """Module-level client using the app's service-principal credentials.

    In Apps the runtime supplies SP creds via the default credential chain. Locally
    we fall back to the configured CLI profile.
    """
    return _local_client()


@lru_cache(maxsize=1)
def _local_client() -> WorkspaceClient:
    settings = get_settings()
    if IS_DATABRICKS_APP:
        return WorkspaceClient()
    return WorkspaceClient(profile=settings.profile) if settings.profile else WorkspaceClient()
