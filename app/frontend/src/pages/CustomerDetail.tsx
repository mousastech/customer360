import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { api } from "../api/client";
import type { CustomerDetail as Detail, CustomerMetrics, Note, Segment } from "../api/types";

type Tab = "profile" | "activity" | "notes" | "segment";

function fmtMoney(n: number) {
  return n.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

export default function CustomerDetail() {
  const { id = "" } = useParams();
  const [tab, setTab] = useState<Tab>("profile");
  const qc = useQueryClient();

  // Fan out the independent per-tab fetches in parallel.
  const [detailQ, metricsQ, notesQ] = useQueries({
    queries: [
      { queryKey: ["customer", id], queryFn: () => api.customer(id), staleTime: 30_000 },
      { queryKey: ["metrics", id], queryFn: () => api.metrics(id), staleTime: 60_000 },
      { queryKey: ["notes", id], queryFn: () => api.notes(id), staleTime: 15_000 },
    ],
  });
  const detail = detailQ.data as Detail | undefined;
  const metrics = metricsQ.data as CustomerMetrics | undefined;
  const notes = notesQ.data as Note[] | undefined;

  const { data: segments } = useQuery<Segment[]>({
    queryKey: ["segments"],
    queryFn: api.segments,
    staleTime: 5 * 60_000,
  });

  if (detailQ.isLoading) return <div className="center-load"><span className="spinner" /></div>;
  if (detailQ.isError || !detail)
    return <div className="error-box">Customer not found: {id}</div>;

  const p = detail.profile;

  return (
    <div>
      <Link to="/customers" className="btn btn-sm" style={{ marginBottom: 14 }}>
        <ArrowLeft size={14} /> Back
      </Link>
      <h1 className="page-title">
        {p.first_name} {p.last_name}{" "}
        <span style={{ color: "var(--text-muted)", fontWeight: 500, fontFamily: "ui-monospace, monospace", fontSize: 15 }}>
          {p.customer_id}
        </span>
      </h1>
      <p className="page-sub">{p.email}</p>

      <div className="tabs">
        {(["profile", "activity", "notes", "segment"] as Tab[]).map((t) => (
          <div key={t} className={`tab ${tab === t ? "active" : ""}`} onClick={() => setTab(t)}>
            {t[0].toUpperCase() + t.slice(1)}
          </div>
        ))}
      </div>

      {tab === "profile" && <ProfileTab p={p} metrics={metrics} loadingMetrics={metricsQ.isLoading} />}
      {tab === "activity" && <ActivityTab detail={detail} />}
      {tab === "notes" && (
        <NotesTab
          id={id}
          notes={notes}
          loading={notesQ.isLoading}
          onAdded={() => {
            qc.invalidateQueries({ queryKey: ["notes", id] });
          }}
        />
      )}
      {tab === "segment" && (
        <SegmentTab id={id} current={p.segment_id ?? ""} segments={segments ?? []} onSaved={() => qc.invalidateQueries({ queryKey: ["customer", id] })} />
      )}
    </div>
  );
}

function ProfileTab({ p, metrics, loadingMetrics }: { p: Detail["profile"]; metrics?: CustomerMetrics; loadingMetrics: boolean }) {
  return (
    <>
      <div className="stat-row">
        <div className="card stat">
          <div className="label">Lifetime spend</div>
          <div className="value">{loadingMetrics ? "…" : fmtMoney(metrics?.lifetime_spend ?? 0)}</div>
        </div>
        <div className="card stat">
          <div className="label">Last 30 days</div>
          <div className="value">{loadingMetrics ? "…" : fmtMoney(metrics?.last_30d ?? 0)}</div>
        </div>
        <div className="card stat">
          <div className="label">Last 90 days</div>
          <div className="value">{loadingMetrics ? "…" : fmtMoney(metrics?.last_90d ?? 0)}</div>
        </div>
        <div className="card stat">
          <div className="label">Open tickets</div>
          <div className="value">{loadingMetrics ? "…" : metrics?.open_tickets ?? 0}</div>
        </div>
        <div className="card stat">
          <div className="label">Avg CSAT</div>
          <div className="value">{loadingMetrics ? "…" : metrics?.avg_csat != null ? metrics.avg_csat.toFixed(1) : "—"}</div>
        </div>
      </div>

      <div className="card card-pad" style={{ marginBottom: 16 }}>
        <dl className="kv">
          <dt>Segment</dt><dd>{p.segment_id ? <span className="chip chip-seg">{p.segment_id}</span> : "—"}</dd>
          <dt>Churn score</dt><dd>{p.churn_score.toFixed(2)}</dd>
          <dt>Lifetime value</dt><dd>{fmtMoney(p.lifetime_value)}</dd>
          <dt>Country / City</dt><dd>{p.country ?? "—"}{p.city ? ` · ${p.city}` : ""}</dd>
          <dt>Phone</dt><dd>{p.phone ?? "—"}</dd>
          <dt>Age / Gender</dt><dd>{p.age ?? "—"}{p.gender ? ` · ${p.gender}` : ""}</dd>
          <dt>Signed up</dt><dd>{p.signup_date ?? "—"}</dd>
          <dt>Last purchase</dt><dd>{p.last_purchase_date ?? "—"}</dd>
        </dl>
      </div>

      {metrics && metrics.top_categories.length > 0 && (
        <div className="card card-pad">
          <div className="label" style={{ color: "var(--text-muted)", fontWeight: 600, marginBottom: 10 }}>
            Top categories
          </div>
          {metrics.top_categories.map((c) => (
            <div key={c.category} style={{ display: "flex", justifyContent: "space-between", padding: "5px 0" }}>
              <span>{c.category}</span>
              <span style={{ fontVariantNumeric: "tabular-nums", fontWeight: 600 }}>{fmtMoney(c.total)}</span>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function ActivityTab({ detail }: { detail: Detail }) {
  if (detail.transactions.length === 0) return <div className="empty">No recent transactions.</div>;
  return (
    <div className="card">
      <table>
        <thead>
          <tr>
            <th>Transaction</th><th>Date</th><th>Channel</th><th>Status</th><th className="num">Amount</th>
          </tr>
        </thead>
        <tbody>
          {detail.transactions.map((t) => (
            <tr key={t.transaction_id} style={{ cursor: "default" }}>
              <td style={{ fontFamily: "ui-monospace, monospace", color: "var(--text-muted)" }}>{t.transaction_id}</td>
              <td>{t.transaction_date ?? "—"}</td>
              <td>{t.channel ?? "—"}</td>
              <td>{t.status ?? "—"}</td>
              <td className="num">{fmtMoney(t.amount)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function NotesTab({ id, notes, loading, onAdded }: { id: string; notes?: Note[]; loading: boolean; onAdded: () => void }) {
  const [text, setText] = useState("");
  const mutation = useMutation({
    mutationFn: () => api.addNote(id, text.trim()),
    onSuccess: () => {
      setText("");
      onAdded();
    },
  });

  return (
    <div>
      <div className="card card-pad" style={{ marginBottom: 16 }}>
        <textarea placeholder="Add a note about this customer…" value={text} onChange={(e) => setText(e.target.value)} />
        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 10 }}>
          <button
            className="btn btn-primary"
            disabled={!text.trim() || mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            {mutation.isPending ? "Saving…" : "Add note"}
          </button>
        </div>
        {mutation.isError && <div className="error-box" style={{ marginTop: 10 }}>{(mutation.error as Error).message}</div>}
      </div>
      {loading ? (
        <div className="center-load"><span className="spinner" /></div>
      ) : !notes || notes.length === 0 ? (
        <div className="empty">No notes yet.</div>
      ) : (
        notes.map((n) => (
          <div className="note" key={n.id}>
            <div>{n.note}</div>
            <div className="meta">
              {n.author_email} · {new Date(n.created_at).toLocaleString()}
              {n.processed && <span className="chip" style={{ marginLeft: 8, background: "#e4f5ee", color: "var(--ok)" }}>merged to gold</span>}
            </div>
          </div>
        ))
      )}
    </div>
  );
}

function SegmentTab({ id, current, segments, onSaved }: { id: string; current: string; segments: Segment[]; onSaved: () => void }) {
  const [choice, setChoice] = useState(current);
  const mutation = useMutation({
    mutationFn: () => api.overrideSegment(id, choice),
    onSuccess: onSaved,
  });
  return (
    <div className="card card-pad" style={{ maxWidth: 480 }}>
      <dl className="kv" style={{ marginBottom: 16 }}>
        <dt>Current segment</dt>
        <dd>{current ? <span className="chip chip-seg">{current}</span> : "—"}</dd>
      </dl>
      <div className="field" style={{ marginBottom: 14 }}>
        <label>Override segment</label>
        <select value={choice} onChange={(e) => setChoice(e.target.value)}>
          {segments.map((s) => (
            <option key={s.segment_id} value={s.segment_id}>
              {s.segment_id} · {s.segment_name}
            </option>
          ))}
        </select>
      </div>
      <button className="btn btn-primary" disabled={!choice || mutation.isPending} onClick={() => mutation.mutate()}>
        {mutation.isPending ? "Saving…" : "Save override"}
      </button>
      {mutation.isSuccess && (
        <span className="status-pill status-ok" style={{ marginLeft: 12 }}>
          Saved{mutation.data && !mutation.data.processed ? " (pending forward-ETL)" : ""}
        </span>
      )}
      {mutation.isError && <div className="error-box" style={{ marginTop: 10 }}>{(mutation.error as Error).message}</div>}
    </div>
  );
}
