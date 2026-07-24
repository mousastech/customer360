"""In-app customer endpoints.

Reads come from Lakebase synced tables via the app SP (sub-10ms). The metrics
endpoint runs cross-table aggregates against Delta gold via the SQL warehouse
using the calling user's OBO identity. Writes go to Lakebase staging tables,
transactionally paired with an append to the audit log.
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..auth import caller_email, obo_client
from ..cache import ttl_cached
from ..config import get_settings
from ..db import lakebase_sp
from ..models import (
    CategorySpend,
    CustomerDetail,
    CustomerListItem,
    CustomerMetrics,
    CustomerProfile,
    Note,
    NoteCreate,
    NoteCreated,
    Page,
    Segment,
    SegmentOverride,
    SegmentOverrideCreate,
    Transaction,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["customers"])
_settings = get_settings()

_LIST_COLS = (
    "customer_id, first_name, last_name, email, country, segment_id, "
    "lifetime_value, churn_score"
)


@router.get("/customers", response_model=Page)
def list_customers(
    segment: str | None = None,
    min_ltv: float | None = None,
    max_churn: float | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> Page:
    """Paginated, filtered list from ``customers_synced`` (Lakebase via app SP)."""
    where: list[str] = []
    params: list[object] = []
    if segment:
        where.append("segment_id = %s")
        params.append(segment)
    if min_ltv is not None:
        where.append("lifetime_value >= %s")
        params.append(min_ltv)
    if max_churn is not None:
        where.append("churn_score <= %s")
        params.append(max_churn)
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    offset = (page - 1) * page_size

    with lakebase_sp().connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT count(*) AS n FROM customers_synced {clause}", params)
        total = cur.fetchone()["n"]
        cur.execute(
            f"SELECT {_LIST_COLS} FROM customers_synced {clause} "
            "ORDER BY lifetime_value DESC, customer_id LIMIT %s OFFSET %s",
            [*params, page_size, offset],
        )
        rows = cur.fetchall()
    return Page(
        items=[CustomerListItem(**r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/customers/{customer_id}", response_model=CustomerDetail)
def get_customer(customer_id: str) -> CustomerDetail:
    """Profile + last 20 transactions from Lakebase synced tables (app SP)."""
    with lakebase_sp().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT customer_id, first_name, last_name, email, phone, country, city, "
            "gender, age, signup_date, last_purchase_date, segment_id, lifetime_value, "
            "churn_score, updated_at FROM customers_synced WHERE customer_id = %s",
            [customer_id],
        )
        prof = cur.fetchone()
        if not prof:
            raise HTTPException(status_code=404, detail="customer not found")
        cur.execute(
            "SELECT transaction_id, product_id, transaction_date, channel, status, amount "
            "FROM transactions_synced WHERE customer_id = %s "
            "ORDER BY transaction_date DESC, transaction_id DESC LIMIT 20",
            [customer_id],
        )
        txns = cur.fetchall()
    return CustomerDetail(
        profile=CustomerProfile(**prof),
        transactions=[Transaction(**t) for t in txns],
    )


@router.get("/customers/{customer_id}/metrics", response_model=CustomerMetrics)
def get_metrics(customer_id: str, request: Request) -> CustomerMetrics:
    """Cross-table aggregates against Delta gold via SQL warehouse (OBO)."""
    from ..warehouse import query

    client = obo_client(request)
    gold = _settings.gold

    agg = query(
        client,
        f"""
        WITH tx AS (
          SELECT amount, transaction_date, product_id
          FROM {gold}.transactions
          WHERE customer_id = :cid AND status = 'completed'
        )
        SELECT
          COALESCE(SUM(amount), 0)                                            AS lifetime_spend,
          COALESCE(SUM(CASE WHEN transaction_date >= current_date() - INTERVAL 30 DAYS
                            THEN amount END), 0)                              AS last_30d,
          COALESCE(SUM(CASE WHEN transaction_date >= current_date() - INTERVAL 90 DAYS
                            THEN amount END), 0)                              AS last_90d
        FROM tx
        """,
        {"cid": customer_id},
    )
    cats = query(
        client,
        f"""
        SELECT p.category AS category, SUM(t.amount) AS total
        FROM {gold}.transactions t
        JOIN {gold}.products p ON p.product_id = t.product_id
        WHERE t.customer_id = :cid AND t.status = 'completed'
        GROUP BY p.category
        ORDER BY total DESC
        LIMIT 5
        """,
        {"cid": customer_id},
    )
    tickets = query(
        client,
        f"""
        SELECT
          COUNT_IF(status != 'closed') AS open_tickets,
          AVG(csat_score)              AS avg_csat
        FROM {gold}.support_tickets
        WHERE customer_id = :cid
        """,
        {"cid": customer_id},
    )
    a = agg[0] if agg else {}
    t = tickets[0] if tickets else {}
    return CustomerMetrics(
        lifetime_spend=float(a.get("lifetime_spend") or 0),
        last_30d=float(a.get("last_30d") or 0),
        last_90d=float(a.get("last_90d") or 0),
        top_categories=[
            CategorySpend(category=c["category"], total=float(c["total"] or 0)) for c in cats
        ],
        open_tickets=int(t.get("open_tickets") or 0),
        avg_csat=(float(t["avg_csat"]) if t.get("avg_csat") is not None else None),
    )


@router.get("/customers/{customer_id}/notes", response_model=list[Note])
def list_notes(customer_id: str) -> list[Note]:
    with lakebase_sp().connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, customer_id, note, author_email, created_at, processed "
            "FROM customer_notes_staging WHERE customer_id = %s ORDER BY created_at DESC",
            [customer_id],
        )
        return [Note(**r) for r in cur.fetchall()]


@router.post("/customers/{customer_id}/notes", response_model=NoteCreated, status_code=201)
def add_note(customer_id: str, body: NoteCreate, request: Request) -> NoteCreated:
    """INSERT note + append audit row in the SAME transaction (app SP)."""
    actor = caller_email(request)
    rid = getattr(request.state, "request_id", None)
    with lakebase_sp().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO customer_notes_staging (customer_id, note, author_email) "
                "VALUES (%s, %s, %s) RETURNING id, created_at",
                [customer_id, body.note, actor],
            )
            row = cur.fetchone()
            cur.execute(
                "INSERT INTO customer_audit_log (actor_email, action, customer_id, detail, request_id) "
                "VALUES (%s, 'add_note', %s, %s, %s)",
                [actor, customer_id, json.dumps({"note_id": row["id"]}), rid],
            )
        conn.commit()
    return NoteCreated(id=row["id"], created_at=row["created_at"])


@router.post("/customers/{customer_id}/segment", response_model=SegmentOverride)
def override_segment(
    customer_id: str, body: SegmentOverrideCreate, request: Request
) -> SegmentOverride:
    """Idempotent UPSERT of segment override + audit row, one transaction (app SP).

    Re-submitting the same segment is a no-op (no duplicate row, override reset to
    unprocessed only when the value actually changes).
    """
    actor = caller_email(request)
    rid = getattr(request.state, "request_id", None)
    with lakebase_sp().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO customer_segment_overrides_staging
                    (customer_id, segment_id, author_email)
                VALUES (%s, %s, %s)
                ON CONFLICT (customer_id) DO UPDATE
                    SET segment_id = EXCLUDED.segment_id,
                        author_email = EXCLUDED.author_email,
                        updated_at = now(),
                        processed = false
                    WHERE customer_segment_overrides_staging.segment_id <> EXCLUDED.segment_id
                RETURNING customer_id, segment_id, author_email, updated_at, processed,
                          (xmax = 0) AS inserted
                """,
                [customer_id, body.segment_id, actor],
            )
            row = cur.fetchone()
            if row is None:
                # No-op update (same value) — return current row without an audit entry.
                cur.execute(
                    "SELECT customer_id, segment_id, author_email, updated_at, processed "
                    "FROM customer_segment_overrides_staging WHERE customer_id = %s",
                    [customer_id],
                )
                current = cur.fetchone()
                conn.commit()
                return SegmentOverride(**current)
            cur.execute(
                "INSERT INTO customer_audit_log (actor_email, action, customer_id, detail, request_id) "
                "VALUES (%s, 'override_segment', %s, %s, %s)",
                [actor, customer_id, json.dumps({"segment_id": body.segment_id}), rid],
            )
        conn.commit()
    return SegmentOverride(
        customer_id=row["customer_id"],
        segment_id=row["segment_id"],
        author_email=row["author_email"],
        updated_at=row["updated_at"],
        processed=row["processed"],
    )


@router.get("/segments", response_model=list[Segment])
@ttl_cached(ttl=300)
def list_segments() -> list[Segment]:
    """Segment reference list (rarely changes) — read from gold via warehouse SP.

    Uses the SP client since it's non-user-specific reference data; cached 5 min.
    """
    from ..auth import sp_client
    from ..warehouse import query

    rows = query(
        sp_client(),
        f"SELECT segment_id, segment_name, description FROM {_settings.gold}.customer_segments "
        "ORDER BY segment_id",
    )
    return [Segment(**r) for r in rows]
