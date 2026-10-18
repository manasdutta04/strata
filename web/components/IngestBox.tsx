"use client";
import { useEffect, useRef, useState } from "react";
import { api, fmtDate, type DocIngestResult, type IngestResult, type TimelineRow } from "@/lib/api";

const EXAMPLE =
  "Heads up: from today we're dropping Kafka and moving the event bus to Redis Streams. Ops cost and on-call load are too high.";
const DOC_TITLE = "Local dev setup for auth-service";
const DOC_EXAMPLE = `Getting auth-service running on your laptop.

Start a local Redis first: user sessions are stored in Redis, so login will fail without it.

Access tokens expire after 15 minutes, so expect to log in again during long debugging sessions.

Pushes run CI on GitHub Actions; check the Actions tab if your branch is red.`;
const STEPS = ["Ingestor", "Steward", "Concierge"] as const;

export default function IngestBox({ onDone }: { onDone: () => void }) {
  const [mode, setMode] = useState<"message" | "doc">("message");
  const [title, setTitle] = useState("");
  const [docResult, setDocResult] = useState<DocIngestResult | null>(null);
  const [text, setText] = useState("");
  const [author, setAuthor] = useState("aisha");
  const [channel, setChannel] = useState("platform");
  const [running, setRunning] = useState(false);
  const [rows, setRows] = useState<TimelineRow[]>([]);
  const [result, setResult] = useState<IngestResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const startedAt = useRef(0);

  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => api.timeline().then(setRows).catch(() => {}), 800);
    return () => clearInterval(t);
  }, [running]);

  const run = rows.filter((r) => r.kind === (mode === "doc" ? "doc_check" : "review") && r.created_at >= startedAt.current - 2000).at(-1);
  const done = !running && (result?.status === "ingested" || !!docResult);
  const stepDone = (s: (typeof STEPS)[number]) =>
    s === "Ingestor" ? !!run : s === "Steward" ? !!run?.handoffs.some((h) => h.agent === "Steward") && !!run?.handoffs.some((h) => h.agent === "Concierge") || run?.status === "done"
      : run?.status === "done";
  const stepActive = (s: (typeof STEPS)[number]) => running && STEPS.find((x) => !stepDone(x)) === s;

  const submit = async () => {
    setRunning(true); setResult(null); setDocResult(null); setError(null); setRows([]);
    startedAt.current = Date.now();
    try {
      if (mode === "doc") setDocResult(await api.ingestDoc(title || "Untitled doc", author, text));
      else setResult(await api.ingest(channel, author, text));
      onDone();
    } catch (e) { setError(String(e)); } finally { setRunning(false); }
  };

  return (
    <div className="card m-4 p-3">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex gap-1 text-sm">
          {(["message", "doc"] as const).map((m) => (
            <button key={m} disabled={running} onClick={() => { setMode(m); setResult(null); setDocResult(null); setText(""); setTitle(""); setAuthor(m === "doc" ? "omar" : "aisha"); }}
              className={`rounded-md px-2 py-0.5 ${mode === m ? "bg-raised font-medium text-ink" : "text-mute hover:text-ink"}`}>
              {m === "message" ? "Slack message" : "New doc"}
            </button>
          ))}
        </div>
        <button className="text-xs text-accent hover:underline" disabled={running}
          onClick={() => (mode === "doc" ? (setTitle(DOC_TITLE), setText(DOC_EXAMPLE)) : setText(EXAMPLE))}>use the live example</button>
      </div>
      {mode === "doc" && (
        <input value={title} onChange={(e) => setTitle(e.target.value)} disabled={running} placeholder="Doc title"
          className="mb-2 w-full rounded-md border border-line bg-raised px-2 py-1.5 text-sm outline-none focus:border-accent" />
      )}
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={mode === "doc" ? 6 : 3} disabled={running}
        placeholder={mode === "doc" ? "Paste a doc draft. Strata checks every statement against the decisions in force before anyone follows it." : "#platform — “from today we are moving …”"}
        className="w-full resize-none rounded-md border border-line bg-raised p-2 text-sm outline-none focus:border-accent" />
      <div className="mt-2 flex items-center gap-2">
        {mode === "message" && (<>
          <span className="text-xs text-mute">#</span>
          <input value={channel} onChange={(e) => setChannel(e.target.value)} className="w-24 rounded-md border border-line bg-raised px-2 py-1 text-xs" />
        </>)}
        <span className="text-xs text-mute">by</span>
        <input value={author} onChange={(e) => setAuthor(e.target.value)} className="w-24 rounded-md border border-line bg-raised px-2 py-1 text-xs" />
        <button className="btn-accent ml-auto" disabled={running || !text.trim()} onClick={submit}>{running ? "Working…" : mode === "doc" ? "Check & ingest" : "Ingest"}</button>
      </div>
      {(running || result || docResult) && (
        <div className="mt-3 flex items-center gap-2 text-xs">
          {STEPS.map((s, i) => (
            <div key={s} className="flex items-center gap-2">
              <span className={`rounded-full border px-2 py-0.5 ${stepDone(s) || done ? "border-ok text-ok" : stepActive(s) ? "pulse border-accent text-accent" : "border-line text-mute"}`}>{s}</span>
              {i < 2 && <span className="text-mute">→</span>}
            </div>
          ))}
        </div>
      )}
      {result?.status === "ingested" && (
        <div className="mt-2 text-xs text-ink">
          <span className="text-ok">{result.decision_id}</span> {result.extraction?.summary}{" "}
          {result.supersedes_id && <>closes <span className="font-mono text-stale">{result.supersedes_id}</span> (kept, not deleted). </>}
          <b>{result.docs} docs + {result.tickets} tickets</b> are now stale.
        </div>
      )}
      {docResult && (
        <div className="mt-2 space-y-1.5 text-xs">
          <div className="text-mute">
            {docResult.checks.length} known facts found{docResult.extraction.system_id && <> about <span className="font-mono text-ink">{docResult.extraction.system_id}</span></>} ·{" "}
            {docResult.conflicts ? <b className="text-stale">{docResult.conflicts} already wrong</b> : <span className="text-ok">all current</span>}
          </div>
          {docResult.checks.map((c) => (
            <div key={c.claim_id} className={`rounded-md px-2 py-1.5 ${c.in_force ? "bg-raised" : "border-l-2 border-stale bg-stale/10"}`}>
              <span className={c.in_force ? "text-ok" : "text-stale"}>{c.in_force ? "✓ current" : "⚠ contradicts"}</span>{" "}
              <span className="text-ink">“{c.quote || c.claim_text}”</span>
              {!c.in_force && c.closed_by && (
                <div className="mt-0.5 text-mute">
                  <span className="font-mono text-accent">{c.closed_by}</span> {c.closed_by_summary} — {c.closed_by_name}, {c.closed_at ? fmtDate(c.closed_at) : ""}
                </div>
              )}
            </div>
          ))}
          {docResult.tasks.length > 0 && <div className="text-mute">The Steward drafted {docResult.tasks.length} fix{docResult.tasks.length > 1 ? "es" : ""} for the author below. Nothing changes without a click.</div>}
        </div>
      )}
      {result?.status === "ignored" && <div className="mt-2 text-xs text-mute">No decision found in that message ({result.reason}).</div>}
      {error && <div className="mt-2 text-xs text-bad">{error}</div>}
    </div>
  );
}
