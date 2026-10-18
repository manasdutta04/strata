"use client";
import { useEffect, useState } from "react";
import { api, fmtDate, type DriftRow, type Health } from "@/lib/api";

const STATUS: Record<string, [string, string]> = {
  open: ["fix awaiting approval", "text-stale"],
  approved: ["fixed", "text-ok"],
  rejected: ["fix rejected", "text-bad"],
};

function Stat({ label, value, tone = "" }: { label: string; value: string | number; tone?: string }) {
  return (
    <div className="card px-3 py-2">
      <div className={`text-lg font-semibold ${tone}`}>{value}</div>
      <div className="text-[11px] text-mute">{label}</div>
    </div>
  );
}

export default function KnowledgeHealth({ refreshKey, onChange, onFocus }: {
  refreshKey: string; onChange: () => void; onFocus: (row: DriftRow) => void;
}) {
  const [h, setH] = useState<Health | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { api.health().then(setH).catch((e) => setError(String(e))); }, [refreshKey]);

  const dispatch = async () => {
    setBusy(true); setError(null);
    try { await api.dispatchAudit(); onChange(); setH(await api.health()); } catch (e) { setError(String(e)); } finally { setBusy(false); }
  };

  if (!h) return <div className="px-4 pb-6 text-sm text-mute">{error ?? <span className="pulse">Auditing the graph…</span>}</div>;
  const tone = h.health >= 95 ? "text-ok" : h.health >= 85 ? "text-stale" : "text-bad";
  return (
    <div className="space-y-4 px-4 pb-6">
      <div>
        <div className="text-sm font-medium">Can you trust what the brain says?</div>
        <div className="text-xs text-mute">A self-audit run as graph queries: every current doc and open ticket is checked against the decisions in force.</div>
      </div>
      <div className="grid grid-cols-3 gap-2">
        <Stat label="docs + tickets still correct" value={`${h.health}%`} tone={tone} />
        <Stat label="contradict a newer decision" value={h.stale_items} tone={h.stale_items ? "text-stale" : "text-ok"} />
        <Stat label="nobody owns" value={h.unowned.length} tone={h.unowned.length ? "text-stale" : "text-ok"} />
      </div>
      <div className="text-[11px] text-mute">
        {h.docs} docs · {h.open_tickets} open tickets · {h.messages} messages · {h.prs} PRs · {h.people} people · {h.in_force}/{h.decisions} decisions in force
        {h.unevidenced > 0 && <span className="text-stale"> · {h.unevidenced} decisions without evidence</span>}
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between">
          <div className="text-sm font-medium">Already wrong</div>
          {h.untracked_stale > 0 && (
            <button className="btn-accent" disabled={busy} onClick={dispatch}>
              {busy ? "Steward drafting…" : `Send ${h.untracked_stale} to the Steward`}
            </button>
          )}
        </div>
        {h.drift.length === 0 && <div className="text-sm text-mute">Nothing contradicts a decision in force.</div>}
        <div className="space-y-2">
          {h.drift.map((r) => {
            const [label, cls] = r.task_status ? STATUS[r.task_status] : ["not tracked yet", "text-mute"];
            return (
              <button key={`${r.item_id}-${r.decision_id}`} onClick={() => onFocus(r)} className="card block w-full p-2.5 text-left hover:border-accent">
                <div className="flex items-start gap-2">
                  <span className="chip shrink-0">{r.item_label}</span>
                  <span className="text-sm">{r.title}</span>
                  <span className={`ml-auto shrink-0 text-[11px] ${cls}`}>{label}</span>
                </div>
                <div className="mt-1.5 text-[11px] text-mute">
                  still says <span className="text-stale">“{r.stale_text}”</span> · since {fmtDate(r.decided_at)}:{" "}
                  <span className="font-mono text-accent">{r.decision_id}</span> {r.decision_summary}
                </div>
                <div className="mt-1 text-[11px] text-mute">Owner <span className="text-ink">{r.owner_name ?? "—"}</span> · {r.routed_via}</div>
              </button>
            );
          })}
        </div>
        {h.untracked_stale > 0 && <div className="mt-2 text-[11px] text-mute">The Steward only drafts fixes. Each one lands in the Drift Inbox for a human to approve.</div>}
      </div>

      {(h.unowned.length > 0 || h.bus_factor.length > 0) && (
        <div>
          <div className="mb-2 text-sm font-medium">Ownership gaps</div>
          <div className="space-y-1.5 text-xs">
            {h.unowned.map((u) => (
              <div key={u.id} className="card px-2.5 py-2"><span className="chip mr-2">{u.label}</span>{u.title} <span className="text-mute">has no owner, so fixes route to the owning team’s top expert.</span></div>
            ))}
            {h.bus_factor.map((b) => (
              <div key={b.system_id} className="card border-stale/50 px-2.5 py-2">
                <span className="font-mono">{b.system_id}</span> <span className="text-mute">is understood only by</span> {b.experts[0]?.name}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
