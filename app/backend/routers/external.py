"""External partner API — M2M access, separate auth boundary from in-app routers.

Partners authenticate as a service principal (OAuth client_credentials), send the
bearer to the Apps proxy, which forwards it as X-Forwarded-Access-Token. This
handler reads Delta gold via the SQL warehouse using THAT caller's bearer (OBO) —
never Lakebase, never the app SP — so warehouse RLS / audit reflect the partner SP.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from ..auth import obo_client
from ..config import get_settings
from ..models import CustomerDetail, CustomerProfile, Transaction
from ..warehouse import query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/external", tags=["external"])
_settings = get_settings()


@router.get("/customers/{customer_id}", response_model=CustomerDetail)
def external_get_customer(customer_id: str, request: Request) -> CustomerDetail:
    """Same shape as the in-app detail endpoint, but sourced from gold via warehouse (OBO)."""
    client = obo_client(request)  # partner SP identity from X-Forwarded-Access-Token
    gold = _settings.gold

    prof_rows = query(
        client,
        f"""
        SELECT customer_id, first_name, last_name, email, phone, country, city, gender,
               age, signup_date, last_purchase_date, segment_id, lifetime_value,
               churn_score, updated_at
        FROM {gold}.customers WHERE customer_id = :cid
        """,
        {"cid": customer_id},
    )
    if not prof_rows:
        raise HTTPException(status_code=404, detail="customer not found")

    txns = query(
        client,
        f"""
        SELECT transaction_id, product_id, transaction_date, channel, status, amount
        FROM {gold}.transactions WHERE customer_id = :cid
        ORDER BY transaction_date DESC, transaction_id DESC LIMIT 20
        """,
        {"cid": customer_id},
    )
    return CustomerDetail(
        profile=CustomerProfile(**_coerce(prof_rows[0])),
        transactions=[Transaction(**_coerce(t)) for t in txns],
    )


def _coerce(row: dict) -> dict:
    """Warehouse returns all values as strings; let Pydantic coerce, but normalise empties."""
    return {k: (None if v == "" else v) for k, v in row.items()}
