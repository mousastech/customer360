import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { api } from "../api/client";

export default function Dashboard() {
  const { data: config, isLoading, isError } = useQuery({
    queryKey: ["config"],
    queryFn: api.config,
    staleTime: 5 * 60_000,
  });

  if (isLoading) return <div className="center-load"><span className="spinner" /></div>;
  if (isError || !config) return <div className="error-box">Could not load dashboard config.</div>;

  const src = `${config.databricks_host}/embed/dashboardsv3/${config.dashboard_id}`;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
        <div>
          <h1 className="page-title">Analytics dashboard</h1>
          <p className="page-sub">Segment LTV, top products, ticket trends, churn distribution.</p>
        </div>
        <a className="btn btn-sm" href={src} target="_blank" rel="noreferrer">
          Open in workspace <ExternalLink size={13} />
        </a>
      </div>
      <div className="iframe-wrap">
        <iframe src={src} title="AI/BI dashboard" />
      </div>
    </div>
  );
}
