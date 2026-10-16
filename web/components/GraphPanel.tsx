"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { GraphEdge, Source } from "@/lib/api";


export type Highlight = { nodes: string[]; edges: [string, string, string][] } | null;
type N = { id: string; label: string; name: string; from: number | null; to: number | null; status: string | null; x?: number; y?: number };
type L = { source: string; target: string; type: string };

const R: Record<string, number> = { System: 9, Decision: 7, Claim: 4, Doc: 5, Ticket: 5, Person: 5, Message: 3 };
const FILL: Record<string, string> = { System: "#cfd5e6", Decision: "#8b9cff", Claim: "#0a0c11", Doc: "#7d869c", Ticket: "#7d869c", Person: "#e7e9ef", Message: "#4a5163" };

export default function GraphPanel(props: {
  edges: GraphEdge[]; asOf: number; highlight: Highlight; selected: Source | null; onSelect: (id: string) => void;
}) {
  const { edges, asOf, highlight, selected, onSelect } = props;
  const box = useRef<HTMLDivElement>(null);
  const fg = useRef<any>(null);
  const [size, setSize] = useState({ w: 800, h: 520 });
  // Loaded after mount (the library needs `window`); loading it by hand keeps the ref usable, unlike next/dynamic.
  const [ForceGraph2D, setForceGraph] = useState<any>(null);
  useEffect(() => { import("react-force-graph-2d").then((m) => setForceGraph(() => m.default)); }, []);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setSize({ w: el.clientWidth, h: el.clientHeight }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Base graph: built once per backend refresh so node objects (and their layout) persist across highlights.
  const { base, asserts, hasNext } = useMemo(() => {
    const nodes = new Map<string, N>();
    const links: L[] = [];
    const asserts = new Map<string, string[]>();
    const hasNext = new Set<string>();
    const add = (id: string, label: string, name: string | null, from: number | null, to: number | null, status: string | null) => {
      if (!nodes.has(id)) nodes.set(id, { id, label, name: name ?? id, from, to, status });
    };
    for (const e of edges) {
      add(e.src, e.src_label, e.src_name, e.src_from, e.src_to, e.src_status);
      add(e.dst, e.dst_label, e.dst_name, e.dst_from, e.dst_to, e.dst_status);
      links.push({ source: e.src, target: e.dst, type: e.type });
      if (e.type === "ASSERTS" || e.type === "CITES") asserts.set(e.src, [...(asserts.get(e.src) ?? []), e.dst]);
      if (e.type === "NEXT_VERSION") hasNext.add(e.src);
    }
    return { base: { nodes: [...nodes.values()], links }, asserts, hasNext };
  }, [edges]);

  // Highlights may reference nodes the base graph lacks (people for expertise answers): add them without resetting the layout.
  const data = useMemo(() => {
    const have = new Set(base.nodes.map((n) => n.id));
    const extraNodes: N[] = [];
    for (const id of highlight?.nodes ?? [])
      if (!have.has(id)) { have.add(id); extraNodes.push({ id, label: /^[a-z]+$/.test(id) ? "Person" : "Message", name: id, from: null, to: null, status: null }); }
    const extraLinks: L[] = (highlight?.edges ?? []).filter(([, t]) => t === "EXPERT_ON" || t === "STALE_AFTER").map(([s, t, d]) => ({ source: s, target: d, type: t }));
    if (!extraNodes.length && !extraLinks.length) return base;
    return { nodes: [...base.nodes, ...extraNodes], links: [...base.links, ...extraLinks] };
  }, [base, highlight]);

  const byId = useMemo(() => new Map(data.nodes.map((n) => [n.id, n])), [data]);
  const hl = useMemo(() => (highlight ? new Set(highlight.nodes) : null), [highlight]);
  const hlEdges = useMemo(() => new Set((highlight?.edges ?? []).map(([s, t, d]) => `${s}|${t}|${d}`)), [highlight]);

  const state = useCallback((n: N) => {
    if (n.label === "Decision" || n.label === "Claim") {
      if (n.from != null && n.from > asOf) return "future";
      if (n.to != null && n.to <= asOf) return "closed";
    }
    return "live";
  }, [asOf]);

  const isStale = useCallback((n: N) => {
    if (n.label !== "Doc" && n.label !== "Ticket") return false;
    if (hasNext.has(n.id) || (n.label === "Ticket" && n.status !== "open")) return false;
    return (asserts.get(n.id) ?? []).some((t) => {
      const x = byId.get(t);
      return !!x && x.to != null && x.to <= asOf && (x.from ?? 0) <= asOf;
    });
  }, [asOf, asserts, byId, hasNext]);

  const alpha = useCallback((n: N) => {
    if (hl) return hl.has(n.id) ? 1 : 0.12;
    const s = state(n);
    return s === "future" ? 0.07 : s === "closed" ? 0.35 : 1;
  }, [hl, state]);

  useEffect(() => {
    const t = setTimeout(() => {
      fg.current?.d3Force("charge")?.strength(-140);
      fg.current?.d3Force("link")?.distance(48);
      fg.current?.d3ReheatSimulation();
    }, 50);
    return () => clearTimeout(t);
  }, [base]);

  useEffect(() => {
    if (!hl || !fg.current) return;
    const t = setTimeout(() => { fg.current?.d3ReheatSimulation(); setTimeout(() => fg.current?.zoomToFit(700, 110, (n: N) => hl.has(n.id) && Number.isFinite(n.x)), 1100); }, 300);
    return () => clearTimeout(t);
  }, [hl, data]);

  const paint = useCallback((n: N, ctx: CanvasRenderingContext2D, scale: number) => {
    const x = n.x ?? 0, y = n.y ?? 0, r = R[n.label] ?? 4;
    ctx.globalAlpha = alpha(n);
    if (hl?.has(n.id)) {
      ctx.beginPath(); ctx.arc(x, y, r + 4, 0, 2 * Math.PI); ctx.fillStyle = "rgba(139,156,255,.25)"; ctx.fill();
    }
    ctx.beginPath();
    if (n.label === "Doc" || n.label === "Ticket") ctx.rect(x - r, y - r, 2 * r, 2 * r);
    else ctx.arc(x, y, r, 0, 2 * Math.PI);
    ctx.fillStyle = FILL[n.label] ?? "#777"; ctx.fill();
    if (n.label === "Claim") { ctx.strokeStyle = "#8b9cff"; ctx.lineWidth = 1.2; ctx.stroke(); }
    if (isStale(n)) { ctx.strokeStyle = "#f2a93b"; ctx.lineWidth = 2; ctx.strokeRect(x - r - 2, y - r - 2, 2 * r + 4, 2 * r + 4); }
    if (selected?.id === n.id) { ctx.strokeStyle = "#fff"; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.arc(x, y, r + 5, 0, 2 * Math.PI); ctx.stroke(); }
    const showLabel = n.label === "System" || hl?.has(n.id) || selected?.id === n.id || (scale > 2.2 && n.label !== "Message");
    if (showLabel) {
      const txt = n.name.length > 26 ? n.name.slice(0, 24) + "…" : n.name;
      ctx.font = `${Math.max(3.2, 11 / scale)}px Inter, sans-serif`;
      ctx.fillStyle = "#e7e9ef"; ctx.textAlign = "center"; ctx.fillText(txt, x, y + r + 9 / scale + 2);
    }
    ctx.globalAlpha = 1;
  }, [alpha, hl, isStale, selected]);

  const linkAlpha = (l: any) => {
    const s = (l.source as N).id ?? l.source, t = (l.target as N).id ?? l.target;
    if (hl) return hlEdges.has(`${s}|${l.type}|${t}`) ? 1 : 0.06;
    const a = byId.get(s), b = byId.get(t);
    return a && b ? Math.min(alpha(a), alpha(b)) : 1;
  };

  return (
    <div ref={box} className="relative h-full w-full overflow-hidden">
      {ForceGraph2D && <ForceGraph2D
        ref={fg}
        width={size.w}
        height={size.h}
        graphData={data}
        backgroundColor="#0a0c11"
        nodeRelSize={4}
        cooldownTicks={120}
        d3VelocityDecay={0.35}
        nodeCanvasObject={paint as any}
        nodePointerAreaPaint={((n: N, color: string, ctx: CanvasRenderingContext2D) => {
          ctx.fillStyle = color; ctx.beginPath(); ctx.arc(n.x ?? 0, n.y ?? 0, (R[n.label] ?? 4) + 3, 0, 2 * Math.PI); ctx.fill();
        }) as any}
        linkColor={(l: any) => {
          const a = linkAlpha(l);
          return l.type === "SUPERSEDES" || l.type === "EXPERT_ON" || l.type === "STALE_AFTER"
            ? `rgba(139,156,255,${a})` : `rgba(138,146,166,${a * 0.5})`;
        }}
        linkWidth={(l: any) => (l.type === "SUPERSEDES" ? 2 : hl && linkAlpha(l) === 1 ? 1.6 : 0.6)}
        linkLineDash={(l: any) => (l.type === "SUPERSEDES" || l.type === "EXPERT_ON" ? [4, 2] : null)}
        linkDirectionalArrowLength={3}
        linkDirectionalArrowRelPos={1}
        onEngineStop={() => { if (!hl) fg.current?.zoomToFit(400, 50); }}
        onNodeClick={(n: any) => onSelect(n.id)}
        nodeLabel={(n: any) => `${n.label}: ${n.name}`}
      />}
      <div className="pointer-events-none absolute left-3 top-3 flex flex-wrap gap-x-3 gap-y-1 rounded-md bg-bg/70 px-2 py-1 text-[11px] text-mute">
        <span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-accent" />decision</span>
        <span><i className="mr-1 inline-block h-2 w-2 rounded-full border border-accent" />claim</span>
        <span><i className="mr-1 inline-block h-2 w-2 bg-[#7d869c]" />doc / ticket</span>
        <span><i className="mr-1 inline-block h-2 w-2 border-2 border-stale" />stale</span>
        <span>dim = closed or not yet true</span>
      </div>
      {selected && (
        <div className="absolute bottom-3 left-3 max-w-md rounded-lg border border-line bg-panel/95 p-3 text-xs shadow-xl">
          <div className="mb-1 flex items-center gap-2">
            <span className="chip">{selected.kind}</span>
            <span className="font-mono text-mute">{selected.id}</span>
            <button className="ml-auto text-mute hover:text-ink" onClick={() => onSelect("")}>✕</button>
          </div>
          <div className="text-ink">{selected.text}</div>
          {selected.url && <a className="mt-1 block truncate text-accent" href={selected.url} target="_blank">{selected.url}</a>}
        </div>
      )}
    </div>
  );
}
