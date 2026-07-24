import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Play, ExternalLink } from "lucide-react";
import { api } from "../api/client";
import type { RunSummary } from "../api/types";

function statusPill(r: RunSummary) {
  const s = r.result ?? r.state ?? "";
  if (s === "SUCCESS" || s === "TERMINATED") return <span className="status-pill status-ok">{r.result ?? "Done"}</span>;
  if (s === "RUNNING" || s === "PENDING" || s === "BLOCKED") return <span className="status-pill status-run">{s}</span>;
  if (s === "FAILED" || s === "ERROR" || s === "TIMEDOUT") return <span className="status-pill status-fail">{s}</span>;
  return <span className="status-pill status-run">{s || "—"}</span>;
}

export default function Reports() {
  const qc = useQueryClient();
  const [lastRun, setLastRun] = useState<number | null>(null);

  const { data: runs, isLoading } = useQuery({
    queryKey: ["job-runs"],
    queryFn: api.jobRuns,
    refetchInterval: (q) => {
      const data = q.state.data as RunSummary[] | undefined;
      const active = data?.some((r) => ["RUNNING", "PENDING", "BLOCKED"].includes(r.state ?? ""));
      return active ? 3000 : false;
    },
  });

  const trigger = useMutation({
    mutationFn: api.runForwardEtl,
    onSuccess: (r) => {
      setLastRun(r.run_id);
      qc.invalidateQueries({ queryKey: ["job-runs"] });
    },
  });

  return (
    <div>
      <h1 className="page-title">Reports · Forward-ETL</h1>
      <p className="page-sub">
        Promote staged notes &amp; segment overrides from Lakebase into Delta gold (psycopg + MERGE INTO).
      </p>

      <div className="card card-pad" style={{ marginBottom: 20, display: "flex", alignItems: "center", gap: 16 }}>
        <button className="btn btn-primary" disabled={trigger.isPending} onClick={() => trigger.mutate()}>
          <Play size={15} /> {trigger.isPending ? "Triggering…" : "Run forward-ETL"}
        </button>
        {lastRun && <span style={{ color: "var(--text-muted)" }}>Triggered run #{lastRun}</span>}
        {trigger.isError && <span className="error-box">{(trigger.error as Error).message}</span>}
      </div>

      <div className="card">
        <div className="card-pad" style={{ borderBottom: "1px solid var(--border)", fontWeight: 700 }}>
          Recent runs
        </div>
        {isLoading ? (
          <div className="center-load"><span className="spinner" /></div>
        ) : !runs || runs.length === 0 ? (
          <div className="empty">No runs yet. Trigger one above.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Run ID</th>
                <th>Status</th>
                <th>Started</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.run_id} style={{ cursor: "default" }}>
                  <td style={{ fontFamily: "ui-monospace, monospace" }}>#{r.run_id}</td>
                  <td>{statusPill(r)}</td>
                  <td>{r.start_time ? new Date(r.start_time).toLocaleString() : "—"}</td>
                  <td className="num">
                    {r.run_page_url && (
                      <a href={r.run_page_url} target="_blank" rel="noreferrer" className="btn btn-sm">
                        View <ExternalLink size={12} />
                      </a>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
