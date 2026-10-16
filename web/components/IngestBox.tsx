"use client";
import { useEffect, useRef, useState } from "react";
import { api, type IngestResult, type TimelineRow } from "@/lib/api";

const EXAMPLE =
  "Heads up: from today we're dropping Kafka and moving the event bus to Redis Streams. Ops cost and on-call load are too high.";
const STEPS = ["Ingestor", "Steward", "Concierge"] as const;

export default function IngestBox({ onDone }: { onDone: () => void }) {
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

  const run = rows.filter((r) => r.kind === "review" && r.created_at >= startedAt.current - 2000).at(-1);
  const stepDone = (s: (typeof STEPS)[number]) =>
    s === "Ingestor" ? !!run : s === "Steward" ? !!run?.handoffs.some((h) => h.agent === "Steward") && !!run?.handoffs.some((h) => h.agent === "Concierge") || run?.status === "done"
      : run?.status === "done";
  const stepActive = (s: (typeof STEPS)[number]) => running && STEPS.find((x) => !stepDone(x)) === s;

  const submit = async () => {
    setRunning(true); setResult(null); setError(null); setRows([]);
    startedAt.current = Date.now();
    try {
      const r = await api.ingest(channel, author, text);
      setResult(r);
      onDone();
    } catch (e) { setError(String(e)); } finally { setRunning(false); }
  };

  return (
    <div className="card m-4 p-3">
      <div className="mb-2 flex items-center justify-between">
        <div className="text-sm font-medium">Paste a Slack message</div>
        <button className="text-xs text-accent hover:underline" onClick={() => setText(EXAMPLE)}>use the live example</button>
      </div>
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={3} disabled={running}
        placeholder="#platform — “from today we are moving …”"
        className="w-full resize-none rounded-md border border-line bg-raised p-2 text-sm outline-none focus:border-accent" />
      <div className="mt-2 flex items-center gap-2">
        <span className="text-xs text-mute">#</span>
        <input value={channel} onChange={(e) => setChannel(e.target.value)} className="w-24 rounded-md border border-line bg-raised px-2 py-1 text-xs" />
        <span className="text-xs text-mute">by</span>
        <input value={author} onChange={(e) => setAuthor(e.target.value)} className="w-24 rounded-md border border-line bg-raised px-2 py-1 text-xs" />
        <button className="btn-accent ml-auto" disabled={running || !text.trim()} onClick={submit}>{running ? "Working…" : "Ingest"}</button>
      </div>
      {(running || result) && (
        <div className="mt-3 flex items-center gap-2 text-xs">
          {STEPS.map((s, i) => (
            <div key={s} className="flex items-center gap-2">
              <span className={`rounded-full border px-2 py-0.5 ${stepDone(s) || (!running && result?.status === "ingested") ? "border-ok text-ok" : stepActive(s) ? "pulse border-accent text-accent" : "border-line text-mute"}`}>{s}</span>
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
      {result?.status === "ignored" && <div className="mt-2 text-xs text-mute">No decision found in that message ({result.reason}).</div>}
      {error && <div className="mt-2 text-xs text-bad">{error}</div>}
    </div>
  );
}
