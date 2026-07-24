"""Forward-ETL job control (T7, Pattern A).

Triggers the psycopg + MERGE INTO job via the Jobs API as the app SP, and polls
run status for the Reports page.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..auth import sp_client
from ..config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/jobs", tags=["jobs"])
_settings = get_settings()


class RunStarted(BaseModel):
    run_id: int


class RunStatus(BaseModel):
    run_id: int
    life_cycle_state: Optional[str] = None
    result_state: Optional[str] = None
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    run_page_url: Optional[str] = None


class RunSummary(BaseModel):
    run_id: int
    state: Optional[str] = None
    result: Optional[str] = None
    start_time: Optional[int] = None
    run_page_url: Optional[str] = None


@router.post("/run-forward-etl", response_model=RunStarted)
def run_forward_etl() -> RunStarted:
    if not _settings.forward_etl_job_id:
        raise HTTPException(status_code=500, detail="FORWARD_ETL_JOB_ID not configured")
    run = sp_client().jobs.run_now(job_id=int(_settings.forward_etl_job_id))
    return RunStarted(run_id=run.run_id)


@router.get("/runs", response_model=list[RunSummary])
def recent_runs(limit: int = 10) -> list[RunSummary]:
    if not _settings.forward_etl_job_id:
        return []
    runs = sp_client().jobs.list_runs(job_id=int(_settings.forward_etl_job_id), limit=limit)
    out: list[RunSummary] = []
    for r in runs:
        st = r.state
        out.append(
            RunSummary(
                run_id=r.run_id,
                state=(st.life_cycle_state.value if st and st.life_cycle_state else None),
                result=(st.result_state.value if st and st.result_state else None),
                start_time=r.start_time,
                run_page_url=r.run_page_url,
            )
        )
    return out


@router.get("/{run_id}", response_model=RunStatus)
def get_run(run_id: int) -> RunStatus:
    r = sp_client().jobs.get_run(run_id=run_id)
    st = r.state
    return RunStatus(
        run_id=run_id,
        life_cycle_state=(st.life_cycle_state.value if st and st.life_cycle_state else None),
        result_state=(st.result_state.value if st and st.result_state else None),
        start_time=r.start_time,
        end_time=r.end_time,
        run_page_url=r.run_page_url,
    )
