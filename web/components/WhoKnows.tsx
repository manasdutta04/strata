"use client";
import { useEffect, useState } from "react";
import { api, type BusFactor, type Expert } from "@/lib/api";

function Bar({ label, value, max }: { label: string; value: number; max: number }) {
  return (
    <div className="flex items-center gap-2 text-[10px] text-mute">
      <span className="w-16">{label}</span>
      <div className="h-1.5 flex-1 rounded bg-raised"><div className="h-1.5 rounded bg-accent" style={{ width: `${Math.min(100, (value / (max || 1)) * 100)}%` }} /></div>
    </div>
  );
}

export default function WhoKnows({ onPick }: { onPick: (system: string, experts: Expert[]) => void }) {
  const [systems, setSystems] = useState<string[]>([]);
  const [system, setSystem] = useState("billing-reconciler");
  const [experts, setExperts] = useState<Expert[]>([]);
  const [bus, setBus] = useState<BusFactor[]>([]);
  const [teams, setTeams] = useState<{ community: number; members: string[] }[]>([]);

  useEffect(() => { api.systems().then(setSystems); api.busFactor().then(setBus); api.informal().then(setTeams); }, []);
  useEffect(() => { api.whoKnows(system).then((e) => { setExperts(e); onPick(system, e); }); /* eslint-disable-next-line */ }, [system]);

  const maxBt = Math.max(...experts.map((e) => e.betweenness), 1);
  const maxPr = Math.max(...experts.map((e) => e.pagerank), 0.0001);
  return (
    <div className="space-y-4 px-4 pb-6">
      {bus.map((b) => (
        <div key={b.system_id} className="card border-stale/50 p-3 text-sm">
          <span className="text-stale">Bus-factor warning</span> · <span className="font-mono">{b.system_id}</span> is understood only by{" "}
          <b>{b.experts[0].name}</b> <span className="text-mute">({b.experts[0].activity} items)</span>
        </div>
      ))}
      <div>
        <label className="mb-1 block text-xs text-mute">Who actually knows…</label>
        <select value={system} onChange={(e) => setSystem(e.target.value)} className="w-full rounded-md border border-line bg-raised px-2 py-1.5 text-sm">
          {systems.map((s) => <option key={s}>{s}</option>)}
        </select>
      </div>
      <div className="space-y-2">
        {experts.slice(0, 5).map((e, i) => (
          <div key={e.person_id} className="card p-3">
            <div className="flex items-center gap-2">
              <span className="text-mute">{i + 1}</span>
              <span className="text-sm font-medium">{e.name}</span>
              {e.knowledge_bridge && <span className="chip border-accent text-accent">knowledge bridge</span>}
              {e.bus_factor_warning && i === 0 && <span className="chip border-stale text-stale">bus factor 1</span>}
              <span className="ml-auto font-mono text-xs text-ink">{e.score.toFixed(3)}</span>
            </div>
            <div className="mt-2 space-y-1">
              <Bar label="activity" value={e.normalised_activity} max={1} />
              <Bar label="PageRank" value={e.pagerank} max={maxPr} />
              <Bar label="betweenness" value={e.betweenness} max={maxBt} />
            </div>
            <div className="mt-1 text-[10px] text-mute">{e.authored} authored · {e.reviewed} reviewed · score = activity × (1 + PageRank)</div>
          </div>
        ))}
      </div>
      <div>
        <div className="mb-1 text-xs text-mute">Informal teams (label propagation over collaboration, not the org chart)</div>
        <div className="space-y-1">
          {teams.filter((t) => t.members.length > 1).map((t) => (
            <div key={t.community} className="rounded-md bg-raised px-2 py-1 text-[11px] text-mute">{t.members.join(" · ")}</div>
          ))}
        </div>
      </div>
    </div>
  );
}
