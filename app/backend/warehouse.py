"""SQL warehouse execution via the Statement Execution API.

Runs against Delta gold using a caller-supplied WorkspaceClient. Callers pass the
OBO client (in-app metrics + external API) so the statement is attributed to the
real user / partner SP in the SQL audit log — never the deploying user.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementParameterListItem, StatementState

from .config import get_settings

logger = logging.getLogger(__name__)
_settings = get_settings()

# Terminal states for statement polling.
_TERMINAL = {StatementState.SUCCEEDED, StatementState.FAILED, StatementState.CANCELED, StatementState.CLOSED}


def query(
    client: WorkspaceClient,
    sql: str,
    params: dict[str, Any] | None = None,
    *,
    timeout_s: int = 30,
) -> list[dict[str, Any]]:
    """Execute ``sql`` on the warehouse as ``client``'s identity; return list of dict rows."""
    parameters = (
        [StatementParameterListItem(name=k, value=None if v is None else str(v)) for k, v in params.items()]
        if params
        else None
    )
    started = time.monotonic()
    resp = client.statement_execution.execute_statement(
        warehouse_id=_settings.warehouse_id,
        statement=sql,
        parameters=parameters,
        wait_timeout="30s",
    )
    statement_id = resp.statement_id
    while resp.status and resp.status.state not in _TERMINAL:
        if time.monotonic() - started > timeout_s:
            client.statement_execution.cancel_execution(statement_id)
            raise TimeoutError(f"warehouse statement {statement_id} exceeded {timeout_s}s")
        time.sleep(0.5)
        resp = client.statement_execution.get_statement(statement_id)

    if not resp.status or resp.status.state != StatementState.SUCCEEDED:
        msg = resp.status.error.message if resp.status and resp.status.error else "unknown error"
        raise RuntimeError(f"warehouse query failed: {msg}")

    elapsed_ms = (time.monotonic() - started) * 1000
    if elapsed_ms > 500:
        logger.warning("slow warehouse query %.0fms: %s params=%s", elapsed_ms, sql, params)

    return _rows_to_dicts(resp)


def _rows_to_dicts(resp) -> list[dict[str, Any]]:
    result = resp.result
    manifest = resp.manifest
    if not result or not result.data_array or not manifest or not manifest.schema:
        return []
    cols = [c.name for c in manifest.schema.columns]
    return [dict(zip(cols, row)) for row in result.data_array]
