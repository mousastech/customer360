"""Lakebase (Provisioned tier) connection pool for the app service principal.

All in-app DB reads/writes run as the SP. Lakebase Postgres OAuth tokens expire
~1h, so we mint a fresh token on every pool connection via a custom connection
class, and recycle connections before expiry (``max_lifetime=2700``).

There is intentionally no OBO variant — Lakebase does not support ``postgres``
OBO scopes (``generate_database_credential`` with a user bearer fails with
"Provided OAuth token does not have required scopes: postgres").
"""
from __future__ import annotations

import logging

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .auth import sp_client
from .config import IS_DATABRICKS_APP, get_settings

logger = logging.getLogger(__name__)
_settings = get_settings()


def _mint_token() -> str:
    """Fresh Lakebase OAuth token for the Provisioned instance, minted as the SP."""
    cred = sp_client().database.generate_database_credential(
        instance_names=[_settings.pg_instance_name]
    )
    return cred.token


def _pg_user() -> str:
    """Postgres role to connect as.

    In Apps this is the SP's client_id (injected as PGUSER). Locally we fall back to
    the developer's workspace email so ``uv run`` works against the same instance.
    """
    if _settings.pg_user:
        return _settings.pg_user
    if not IS_DATABRICKS_APP:
        try:
            return sp_client().current_user.me().user_name or ""
        except Exception:  # pragma: no cover
            return ""
    return ""


class _OAuthConnection(psycopg.Connection):
    """Connection subclass that injects a fresh OAuth token as the password."""

    @classmethod
    def connect(cls, conninfo: str = "", **kwargs):  # type: ignore[override]
        kwargs["password"] = _mint_token()
        return super().connect(conninfo, **kwargs)


_conninfo = (
    f"dbname={_settings.pg_database} "
    f"user={_pg_user()} "
    f"host={_settings.pg_host} "
    f"port={_settings.pg_port} "
    f"sslmode={_settings.pg_sslmode}"
)

# Deferred open — opened in the FastAPI lifespan so import never blocks.
pool: ConnectionPool = ConnectionPool(
    conninfo=_conninfo,
    connection_class=_OAuthConnection,
    kwargs={"row_factory": dict_row, "connect_timeout": 10},
    min_size=2,
    max_size=10,
    max_lifetime=2700,  # 45 min — recycle before the 1h token expires
    open=False,
)


def lakebase_sp() -> ConnectionPool:
    """Return the shared SP connection pool (opened in app lifespan)."""
    return pool
