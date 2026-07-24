"""FastAPI entry point for the Customer 360 app."""
from __future__ import annotations

import logging
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .auth import caller_email, sp_client
from .cache import ttl_cached
from .config import get_settings
from .db import lakebase_sp
from .models import AppConfig
from .routers import customers, external, genie, jobs

logging.basicConfig(
    level=logging.INFO,
    format='{"level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
)
logger = logging.getLogger("customer360")
_settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    lakebase_sp().open(wait=True, timeout=30.0)
    logger.info("lakebase pool opened")
    yield
    lakebase_sp().close()
    logger.info("lakebase pool closed")


app = FastAPI(title="Customer 360", version="1.0.0", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def request_context(request: Request, call_next):
    """Attach/echo X-Request-Id and set Cache-Control on idempotent GETs."""
    rid = request.headers.get("X-Request-Id") or uuid.uuid4().hex
    request.state.request_id = rid
    response = await call_next(request)
    response.headers["X-Request-Id"] = rid
    if request.method == "GET" and request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "private, max-age=10, must-revalidate")
    return response


app.include_router(customers.router)
app.include_router(genie.router)
app.include_router(external.router)
app.include_router(jobs.router)


@ttl_cached(ttl=300)
def _config_cached() -> AppConfig:
    return AppConfig(
        databricks_host=_settings.host,
        dashboard_id=_settings.dashboard_id,
        genie_space_id=_settings.genie_space_id,
    )


@app.get("/api/config", response_model=AppConfig)
def get_config(request: Request) -> AppConfig:
    cfg = _config_cached()
    # user_email is per-request (not cached).
    return cfg.model_copy(update={"user_email": caller_email(request)})


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/me")
def whoami(request: Request):
    """T2 done-when check: OBO returns the *calling user*, SP endpoint runs as SP."""
    from .auth import obo_client

    obo = obo_client(request).current_user.me()
    sp = sp_client().current_user.me()
    return {
        "obo_user": obo.user_name,
        "sp_identity": sp.user_name,
    }


# --- Static frontend (built bundle committed to backend/static) ---
_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    _assets = os.path.join(_static_dir, "assets")
    if os.path.isdir(_assets):
        app.mount("/assets", StaticFiles(directory=_assets), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "not found"}, status_code=404)
        index = os.path.join(_static_dir, "index.html")
        if os.path.isfile(index):
            return FileResponse(index)
        return JSONResponse({"detail": "frontend not built"}, status_code=404)
