import { memo, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api, type CustomerFilters } from "../api/client";
import type { CustomerListItem, Segment } from "../api/types";

const PAGE_SIZE = 25;

function useDebounced<T>(value: T, ms = 250): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

function fmtMoney(n: number) {
  return n.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

function riskColor(score: number) {
  if (score >= 0.7) return "var(--danger)";
  if (score >= 0.4) return "var(--warn)";
  return "var(--ok)";
}

const Row = memo(function Row({
  c,
  onClick,
}: {
  c: CustomerListItem;
  onClick: (id: string) => void;
}) {
  return (
    <tr onClick={() => onClick(c.customer_id)}>
      <td style={{ fontFamily: "ui-monospace, monospace", color: "var(--text-muted)" }}>{c.customer_id}</td>
      <td style={{ fontWeight: 600 }}>
        {c.first_name} {c.last_name}
      </td>
      <td>{c.email}</td>
      <td>{c.country ?? "—"}</td>
      <td>{c.segment_id ? <span className="chip chip-seg">{c.segment_id}</span> : "—"}</td>
      <td className="num">{fmtMoney(c.lifetime_value)}</td>
      <td className="num">
        <span className="risk">
          <span className="risk-bar">
            <span style={{ width: `${Math.round(c.churn_score * 100)}%`, background: riskColor(c.churn_score) }} />
          </span>
          {c.churn_score.toFixed(2)}
        </span>
      </td>
    </tr>
  );
});

export default function Customers() {
  const navigate = useNavigate();
  const [segment, setSegment] = useState("");
  const [minLtv, setMinLtv] = useState("");
  const [maxChurn, setMaxChurn] = useState("");
  const [page, setPage] = useState(1);

  const dSegment = segment;
  const dMinLtv = useDebounced(minLtv);
  const dMaxChurn = useDebounced(maxChurn);

  useEffect(() => setPage(1), [dSegment, dMinLtv, dMaxChurn]);

  const { data: segments } = useQuery<Segment[]>({
    queryKey: ["segments"],
    queryFn: api.segments,
    staleTime: 5 * 60_000,
  });

  const filters: CustomerFilters = useMemo(
    () => ({
      segment: dSegment || undefined,
      min_ltv: dMinLtv ? Number(dMinLtv) : undefined,
      max_churn: dMaxChurn ? Number(dMaxChurn) : undefined,
      page,
      page_size: PAGE_SIZE,
    }),
    [dSegment, dMinLtv, dMaxChurn, page],
  );

  const { data, isLoading, isError, error, isFetching } = useQuery({
    queryKey: ["customers", filters],
    queryFn: () => api.customers(filters),
    placeholderData: keepPreviousData,
    staleTime: 10_000,
  });

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <div>
      <h1 className="page-title">Customers</h1>
      <p className="page-sub">Browse and drill into Acme Retail accounts.</p>

      <div className="filters">
        <div className="field">
          <label>Segment</label>
          <select value={segment} onChange={(e) => setSegment(e.target.value)}>
            <option value="">All segments</option>
            {segments?.map((s) => (
              <option key={s.segment_id} value={s.segment_id}>
                {s.segment_id} · {s.segment_name}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Min lifetime value</label>
          <input type="number" placeholder="0" value={minLtv} onChange={(e) => setMinLtv(e.target.value)} />
        </div>
        <div className="field">
          <label>Max churn risk</label>
          <input
            type="number"
            step="0.05"
            min="0"
            max="1"
            placeholder="1.0"
            value={maxChurn}
            onChange={(e) => setMaxChurn(e.target.value)}
          />
        </div>
        {isFetching && <span className="spinner" style={{ marginBottom: 8 }} />}
      </div>

      <div className="card">
        {isError ? (
          <div className="card-pad">
            <div className="error-box">Failed to load customers: {(error as Error).message}</div>
          </div>
        ) : isLoading ? (
          <div className="center-load"><span className="spinner" /></div>
        ) : !data || data.items.length === 0 ? (
          <div className="empty">No customers match these filters.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Name</th>
                <th>Email</th>
                <th>Country</th>
                <th>Segment</th>
                <th className="num">Lifetime value</th>
                <th className="num">Churn risk</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((c) => (
                <Row key={c.customer_id} c={c} onClick={(id) => navigate(`/customers/${id}`)} />
              ))}
            </tbody>
          </table>
        )}
      </div>

      {data && (
        <div className="pager">
          <span>
            {data.total.toLocaleString()} customers · page {page} of {totalPages}
          </span>
          <div className="pager-controls">
            <button className="btn btn-sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              ← Prev
            </button>
            <button className="btn btn-sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
