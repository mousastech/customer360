import type {
  AppConfig,
  CustomerDetail,
  CustomerListItem,
  CustomerMetrics,
  GenieConversation,
  GenieMessageResult,
  Note,
  Page,
  RunStatus,
  RunSummary,
  Segment,
  SegmentOverride,
} from "./types";

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export interface CustomerFilters {
  segment?: string;
  min_ltv?: number;
  max_churn?: number;
  page: number;
  page_size: number;
}

export const api = {
  config: () => http<AppConfig>("/api/config"),
  segments: () => http<Segment[]>("/api/segments"),

  customers: (f: CustomerFilters) => {
    const p = new URLSearchParams();
    if (f.segment) p.set("segment", f.segment);
    if (f.min_ltv != null) p.set("min_ltv", String(f.min_ltv));
    if (f.max_churn != null) p.set("max_churn", String(f.max_churn));
    p.set("page", String(f.page));
    p.set("page_size", String(f.page_size));
    return http<Page<CustomerListItem>>(`/api/customers?${p.toString()}`);
  },
  customer: (id: string) => http<CustomerDetail>(`/api/customers/${id}`),
  metrics: (id: string) => http<CustomerMetrics>(`/api/customers/${id}/metrics`),
  notes: (id: string) => http<Note[]>(`/api/customers/${id}/notes`),
  addNote: (id: string, note: string) =>
    http<{ id: number; created_at: string }>(`/api/customers/${id}/notes`, {
      method: "POST",
      body: JSON.stringify({ note }),
    }),
  overrideSegment: (id: string, segment_id: string) =>
    http<SegmentOverride>(`/api/customers/${id}/segment`, {
      method: "POST",
      body: JSON.stringify({ segment_id }),
    }),

  genieStart: (content: string) =>
    http<GenieConversation>("/api/genie/conversations", {
      method: "POST",
      body: JSON.stringify({ content }),
    }),
  genieReply: (conversationId: string, content: string) =>
    http<GenieConversation>(`/api/genie/conversations/${conversationId}/messages`, {
      method: "POST",
      body: JSON.stringify({ content }),
    }),
  genieMessage: (conversationId: string, messageId: string) =>
    http<GenieMessageResult>(
      `/api/genie/conversations/${conversationId}/messages/${messageId}`,
    ),

  runForwardEtl: () =>
    http<{ run_id: number }>("/api/jobs/run-forward-etl", { method: "POST" }),
  jobRuns: () => http<RunSummary[]>("/api/jobs/runs"),
  jobRun: (runId: number) => http<RunStatus>(`/api/jobs/${runId}`),
};
