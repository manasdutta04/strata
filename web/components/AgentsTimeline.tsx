"use client";
import { fmtTime, type TimelineRow } from "@/lib/api";

export default function AgentsTimeline({ rows }: { rows: TimelineRow[] }) {
  const runs = rows.filter((r) => r.kind === "review");
  const drift = rows.filter((r) => r.kind === "drift_fix");
  return (
    <div className="space-y-3 px-4 pb-6">
      <div className="text-xs text-mute">Agents share state only through Task nodes in the graph. A restart resumes from Task status.</div>
      {runs.length === 0 && <div className="text-sm text-mute">No runs yet. Ingest a message to watch the hand-off.</div>}
      {runs.map((r) => {
        const chain = [{ agent: r.created_by ?? "Ingestor", ts: r.created_at, verb: "created" }, ...r.handoffs.map((h) => ({ ...h, verb: "handed to" }))];
        return (
          <div key={r.task_id} className="card p-3">
            <div className="mb-2 flex items-center gap-2 text-xs">
              <span className="font-mono text-ink">{r.task_id}</span>
              <span className={`ml-auto ${r.status === "done" ? "text-ok" : "text-stale"}`}>{r.status}</span>
            </div>
            <ol className="space-y-1.5 border-l border-line pl-3">
              {chain.map((c, i) => (
                <li key={i} className="relative text-xs">
                  <span className="absolute -left-[17px] top-1 h-2 w-2 rounded-full bg-accent" />
                  <span className="text-mute">{c.verb} </span><span className="font-medium text-ink">{c.agent}</span>
                  <span className="ml-2 font-mono text-[10px] text-mute">{fmtTime(c.ts)}</span>
                </li>
              ))}
            </ol>
          </div>
        );
      })}
      {drift.length > 0 && (
        <div className="text-xs text-mute">
          Steward created {drift.length} drift tasks ({drift.filter((d) => d.status === "open").length} open,{" "}
          {drift.filter((d) => d.status === "approved").length} approved, {drift.filter((d) => d.status === "rejected").length} rejected).
        </div>
      )}
    </div>
  );
}
