import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Sparkles, X, Maximize2, Minimize2, ExternalLink, Send } from "lucide-react";
import { api } from "../api/client";
import type { GenieMessageResult } from "../api/types";

interface ChatMsg {
  role: "user" | "genie";
  text: string;
  query?: string | null;
  columns?: string[] | null;
  rows?: unknown[][] | null;
  error?: boolean;
}

const POLL_INTERVAL = 1200;
const POLL_TIMEOUT_MS = 30_000;

export default function GenieWidget() {
  const [open, setOpen] = useState(false);
  const [enlarged, setEnlarged] = useState(false);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const conversationId = useRef<string | null>(null);
  const bodyRef = useRef<HTMLDivElement>(null);

  const { data: config } = useQuery({ queryKey: ["config"], queryFn: api.config, staleTime: 5 * 60_000 });
  const genieUrl = config
    ? `${config.databricks_host}/genie/rooms/${config.genie_space_id}`
    : undefined;

  useEffect(() => {
    bodyRef.current?.scrollTo({ top: bodyRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, busy]);

  async function poll(convId: string, msgId: string): Promise<GenieMessageResult> {
    const start = Date.now();
    while (Date.now() - start < POLL_TIMEOUT_MS) {
      const res = await api.genieMessage(convId, msgId);
      if (["COMPLETED", "FAILED", "CANCELLED"].includes(res.status)) return res;
      await new Promise((r) => setTimeout(r, POLL_INTERVAL));
    }
    return { status: "TIMEOUT", error: "Genie took too long to respond." };
  }

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text }]);
    setBusy(true);
    try {
      const conv = conversationId.current
        ? await api.genieReply(conversationId.current, text)
        : await api.genieStart(text);
      conversationId.current = conv.conversation_id;
      const res = await poll(conv.conversation_id, conv.message_id);
      if (res.status === "COMPLETED") {
        setMessages((m) => [
          ...m,
          {
            role: "genie",
            text: res.content ?? "(no text answer — see result below)",
            query: res.query,
            columns: res.columns,
            rows: res.rows,
          },
        ]);
      } else {
        setMessages((m) => [...m, { role: "genie", text: res.error ?? "Genie could not answer.", error: true }]);
      }
    } catch (e) {
      setMessages((m) => [...m, { role: "genie", text: (e as Error).message, error: true }]);
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button className="genie-fab" onClick={() => setOpen(true)}>
        <Sparkles size={18} /> Ask Genie
      </button>
    );
  }

  return (
    <div className={`genie-panel ${enlarged ? "enlarged" : ""}`}>
      <div className="genie-head">
        <span className="title"><Sparkles size={16} color="var(--brand)" /> Ask Genie</span>
        <div className="actions">
          {enlarged && genieUrl && (
            <a className="icon-btn" href={genieUrl} target="_blank" rel="noreferrer" title="Open in workspace">
              <ExternalLink size={16} />
            </a>
          )}
          <button className="icon-btn" onClick={() => setEnlarged((e) => !e)} title={enlarged ? "Shrink" : "Enlarge"}>
            {enlarged ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
          </button>
          <button className="icon-btn" onClick={() => setOpen(false)} title="Close">
            <X size={16} />
          </button>
        </div>
      </div>

      <div className="genie-body" ref={bodyRef}>
        {messages.length === 0 && (
          <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
            Ask about Acme Retail data — e.g. <em>"Top 5 segments by LTV last quarter"</em> or{" "}
            <em>"Which customers in EU have churn &gt; 0.7?"</em>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`} style={m.error ? { background: "#fdecea", color: "var(--danger)" } : undefined}>
            {m.text}
            {m.query && <div className="sql">{m.query}</div>}
            {m.columns && m.rows && m.rows.length > 0 && (
              <div className="result-table">
                <table>
                  <thead>
                    <tr>{m.columns.map((c) => <th key={c}>{c}</th>)}</tr>
                  </thead>
                  <tbody>
                    {m.rows.slice(0, 10).map((row, ri) => (
                      <tr key={ri}>{(row as unknown[]).map((v, ci) => <td key={ci}>{String(v ?? "")}</td>)}</tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ))}
        {busy && (
          <div className="msg genie">
            <span className="typing"><span /><span /><span /></span>
          </div>
        )}
      </div>

      <div className="genie-foot">
        <input
          placeholder="Ask a question…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          disabled={busy}
        />
        <button className="btn btn-primary" onClick={send} disabled={busy || !input.trim()}>
          <Send size={15} />
        </button>
      </div>
    </div>
  );
}
