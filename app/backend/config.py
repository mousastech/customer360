"""Runtime configuration, loaded from environment (app.yaml env / local .env)."""
from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

# Local dev: load app/.env. In Databricks Apps the runtime injects env directly.
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# True when running inside the Databricks Apps runtime.
IS_DATABRICKS_APP = bool(os.environ.get("DATABRICKS_APP_NAME"))


class Settings:
    """Typed accessors over env vars. Fail loud on missing required values."""

    def __init__(self) -> None:
        self.host = self._host()
        self.profile = os.environ.get("DATABRICKS_PROFILE")  # local only
        self.catalog = os.environ.get("CAPSTONE_CATALOG", "mozuca")
        self.schema = os.environ.get("CAPSTONE_SCHEMA", "gold")
        self.warehouse_id = os.environ.get("WAREHOUSE_ID", "")
        self.dashboard_id = os.environ.get("DASHBOARD_ID", "")
        self.genie_space_id = os.environ.get("GENIE_SPACE_ID", "")
        self.forward_etl_job_id = os.environ.get("FORWARD_ETL_JOB_ID", "")

        # Lakebase (Provisioned instance capstone-pg / capstone_db)
        self.pg_host = os.environ.get("PGHOST", "")
        self.pg_database = os.environ.get("PGDATABASE", "capstone_db")
        self.pg_port = os.environ.get("PGPORT", "5432")
        self.pg_instance_name = os.environ.get("PG_INSTANCE_NAME", "capstone-pg")
        self.pg_sslmode = os.environ.get("PGSSLMODE", "require")
        # In Apps, the runtime injects PGUSER = app SP client_id. Empty locally.
        self.pg_user = os.environ.get("PGUSER", "")

    @staticmethod
    def _host() -> str:
        host = os.environ.get("DATABRICKS_HOST", "")
        # In Apps DATABRICKS_HOST is a bare hostname; add scheme.
        if host and not host.startswith("http"):
            host = f"https://{host}"
        return host

    @property
    def gold(self) -> str:
        return f"{self.catalog}.{self.schema}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
