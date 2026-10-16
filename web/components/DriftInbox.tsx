"use client";
import { useState } from "react";
import { api, type InboxItem } from "@/lib/api";

function Diff({ text }: { text: string }) {
  return (
    <pre className="overflow-x-auto rounded-md bg-bg p-2 font-mono text-[11px] leading-relaxed">
      {text.split("\n").map((l, i) => (
        <div key={i} className={l.startsWith("+") ? "bg-ok/10 text-ok" : l.startsWith("-") ? "bg-bad/10 text-bad" : "text-mute"}>{l || " "}</div>
      ))}
    </pre>
  );
}

export default function DriftInbox({ items, onChange, onFocus }: { items: InboxItem[]; onChange: () => void; onFocus: (item: InboxItem) => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  const act = async (id: string, kind: "approve" | "reject") => {
    setBusy(id);
    try { await (kind === "approve" ? api.approve(id) : api.reject(id)); onChange(); } finally { setBusy(null); }
  };
  if (items.length === 0)
    return <div className="px-4 pb-6 text-sm text-mute">Nothing is stale. Paste a message that reverses a decision and the Steward will find every doc and ticket that just became wrong.</div>;

  const open = items.filter((i) => i.status === "open").length;
  return (
    <div className="space-y-3 px-4 pb-6">
      <div className="text-xs text-mute">{open} awaiting your approval · nothing changes without a click</div>
      {items.map((it) => (
        <div key={it.task_id} className={`card p-3 ${it.status !== "open" ? "opacity-70" : ""}`}>
          <div className="flex items-start gap-2">
            <span className="chip shrink-0">{it.item_label}</span>
            <button className="text-left text-sm font-medium hover:text-accent" onClick={() => onFocus(it)}>{it.item_title}</button>
            <span className={`ml-auto shrink-0 text-[11px] ${it.status === "approved" ? "text-ok" : it.status === "rejected" ? "text-bad" : "text-stale"}`}>{it.status}</span>
          </div>
          {it.why_stale && (
            <div className="mt-2 rounded-md bg-raised px-2 py-1.5 text-[11px] text-mute">
              <span className="font-mono text-ink">{it.item_id}</span> —{it.why_stale.how}→ <span className="text-stale">“{it.why_stale.stale_text}”</span>
              <br />closed by <span className="font-mono text-accent">{it.why_stale.new_decision_id}</span>: {it.decision_summary}
            </div>
          )}
          <div className="mt-2 text-xs text-mute">Owner <span className="text-ink">{it.owner_name}</span></div>
          <div className="mt-2"><Diff text={it.draft} /></div>
          {it.status === "open" && (
            <div className="mt-2 flex gap-2">
              <button className="btn-accent" disabled={busy === it.task_id} onClick={() => act(it.task_id, "approve")}>Approve</button>
              <button className="btn" disabled={busy === it.task_id} onClick={() => act(it.task_id, "reject")}>Reject</button>
            </div>
          )}
          {it.status === "approved" && <div className="mt-2 text-[11px] text-ok">New version created: {it.item_id}@{it.decision_id} — the old version is kept in the graph.</div>}
        </div>
      ))}
    </div>
  );
}
