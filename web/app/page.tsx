"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import AgentsTimeline from "@/components/AgentsTimeline";
import Chat from "@/components/Chat";
import DriftInbox from "@/components/DriftInbox";
import GraphPanel, { type Highlight } from "@/components/GraphPanel";
import IngestBox from "@/components/IngestBox";
import TimeSlider from "@/components/TimeSlider";
import WhoKnows from "@/components/WhoKnows";
import { api, fmtDate, type Answer, type Expert, type GraphEdge, type InboxItem, type SessionChange, type Source, type TimelineRow } from "@/lib/api";

type Tab = "inbox" | "who" | "agents";
const MIN_T = Date.UTC(2026, 1, 1);

export default function Home() {
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [inbox, setInbox] = useState<InboxItem[]>([]);
  const [timeline, setTimeline] = useState<TimelineRow[]>([]);
  const [sessionId, setSessionId] = useState("default");
  const [changes, setChanges] = useState<SessionChange[]>([]);
  const [asOf, setAsOf] = useState<number | null>(null);
  const [highlight, setHighlight] = useState<Highlight>(null);
  const [selected, setSelected] = useState<Source | null>(null);
  const [tab, setTab] = useState<Tab>("inbox");
  const [offline, setOffline] = useState(false);
  const [now, setNow] = useState(0); // set after mount to avoid a hydration mismatch

  const refresh = useCallback(async () => {
    try {
      const [g, i, t] = await Promise.all([api.graph(), api.inbox(), api.timeline()]);
      setEdges(g); setInbox(i); setTimeline(t); setNow(Date.now()); setOffline(false);
    } catch { setOffline(true); }
  }, []);

  useEffect(() => {
    setNow(Date.now());
    refresh();
    api.startSession().then((s) => { setSessionId(s.session_id); setChanges(s.changes); }).catch(() => {});
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, [refresh]);

  const markers = useMemo(() => {
    const seen = new Map<string, { ts: number; label: string }>();
    for (const e of edges) {
      if (e.src_label === "Decision" && e.src_from) seen.set(e.src, { ts: e.src_from, label: e.src_name ?? e.src });
    }
    return [...seen.values()];
  }, [edges]);

  const selectById = (id: string, a?: Answer) => {
    if (!id) return setSelected(null);
    const fromAnswer = a?.sources.find((s) => s.id === id);
    if (fromAnswer) return setSelected(fromAnswer);
    const e = edges.find((x) => x.src === id || x.dst === id);
    if (!e) return setSelected(null);
    const isSrc = e.src === id;
    setSelected({ id, kind: isSrc ? e.src_label : e.dst_label, text: (isSrc ? e.src_name : e.dst_name) ?? id, url: null });
  };

  const focusItem = (it: InboxItem) => {
    const w = it.why_stale;
    if (!w) return setHighlight({ nodes: [it.item_id, it.decision_id], edges: [] });
    const e: [string, string, string][] = [[it.item_id, w.how, w.stale_id], [w.new_decision_id, "SUPERSEDES", w.old_decision_id]];
    if (w.stale_id.startsWith("C-")) e.push([w.old_decision_id, "ESTABLISHES", w.stale_id]);
    setHighlight({ nodes: [it.item_id, w.stale_id, w.old_decision_id, w.new_decision_id], edges: e });
  };

  const pickExperts = useCallback((system: string, experts: Expert[]) => {
    const top = experts.slice(0, 4);
    setHighlight({ nodes: [system, ...top.map((e) => e.person_id)], edges: top.map((e) => [e.person_id, "EXPERT_ON", system]) });
  }, []);

  const open = inbox.filter((i) => i.status === "open").length;
  const reset = async () => {
    if (!confirm("Reset the demo graph to the seed data? Ingested decisions and approvals are removed.")) return;
    await api.reset(); window.location.reload();
  };

  return (
    <div className="flex h-screen flex-col">
      <header className="flex h-12 shrink-0 items-center gap-3 border-b border-line px-4">
        <div className="text-base font-semibold tracking-tight">Strata</div>
        <div className="hidden text-xs text-mute md:block">the company brain that knows when it’s wrong</div>
        <span className="chip ml-2 border-stale/60 text-stale">Synthetic data · Northwind Labs</span>
        <span className="chip">FalkorDB graph</span>
        {offline && <span className="chip border-bad text-bad">backend offline</span>}
        <button className="ml-auto text-xs text-mute hover:text-ink" onClick={reset}>Reset demo</button>
      </header>

      {changes.length > 0 && (
        <div className="flex items-start gap-3 border-b border-accent/40 bg-accent/10 px-4 py-2 text-sm">
          <span className="text-accent">Memory</span>
          <div className="flex-1">
            {changes.map((c) => (
              <div key={c.system_id}>
                Since you last asked “{c.question}”, that decision changed on {fmtDate(c.changed_at)}: <b>{c.summary}</b>
              </div>
            ))}
          </div>
          <button className="text-mute hover:text-ink" onClick={() => setChanges([])}>✕</button>
        </div>
      )}

      <main className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[400px_minmax(0,1fr)_430px]">
        <section className="flex min-h-0 flex-col border-r border-line">
          <Chat sessionId={sessionId} asOf={asOf}
            onAnswer={(a) => { setHighlight(a.path.nodes.length ? a.path : null); setSelected(null); }}
            onSelectSource={(id, a) => selectById(id, a)} />
        </section>

        <section className="flex min-h-0 flex-col">
          <div className="min-h-0 flex-1">
            <GraphPanel edges={edges} asOf={asOf ?? (now || Number.MAX_SAFE_INTEGER)} highlight={highlight} selected={selected} onSelect={(id) => selectById(id)} />
          </div>
          <TimeSlider min={MIN_T} max={now || MIN_T + 86400000} value={asOf} markers={markers} onChange={setAsOf} />
        </section>

        <section className="flex min-h-0 flex-col border-l border-line">
          <nav className="flex shrink-0 border-b border-line px-2">
            <button className={`tab ${tab === "inbox" ? "tab-on" : ""}`} onClick={() => setTab("inbox")}>
              Drift Inbox{open > 0 && <span className="ml-1.5 rounded-full bg-stale px-1.5 text-[10px] font-semibold text-bg">{open}</span>}
            </button>
            <button className={`tab ${tab === "who" ? "tab-on" : ""}`} onClick={() => setTab("who")}>Who Knows</button>
            <button className={`tab ${tab === "agents" ? "tab-on" : ""}`} onClick={() => setTab("agents")}>Agents</button>
          </nav>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {tab === "inbox" && (<><IngestBox onDone={refresh} /><DriftInbox items={inbox} onChange={refresh} onFocus={focusItem} /></>)}
            {tab === "who" && <div className="pt-4"><WhoKnows onPick={pickExperts} /></div>}
            {tab === "agents" && <div className="pt-4"><AgentsTimeline rows={timeline} /></div>}
          </div>
        </section>
      </main>
    </div>
  );
}
