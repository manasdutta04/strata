export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Segment = { text: string; sources: string[]; tone?: "normal" | "warning" };
export type Source = { id: string; kind: string; text: string; url: string | null };
export type Answer = {
  question: string;
  tool: string;
  found: boolean;
  text: string;
  segments: Segment[];
  path: { nodes: string[]; edges: [string, string, string][]; labels?: Record<string, string> };
  sources: Source[];
  searched: string[];
  as_of: number;
};
export type GraphEdge = {
  src: string; src_label: string; src_name: string | null; src_from: number | null; src_to: number | null; src_status: string | null;
  dst: string; dst_label: string; dst_name: string | null; dst_from: number | null; dst_to: number | null; dst_status: string | null;
  type: string; ts: number | null;
};
export type InboxItem = {
  task_id: string; status: "open" | "approved" | "rejected"; draft: string; updated_at: number;
  item_id: string; item_label: string; item_title: string;
  decision_id: string; decision_summary: string; old_decision_id: string | null; old_summary: string | null;
  owner_id: string; owner_name: string;
  why_stale: { how: string; stale_id: string; stale_text: string; old_decision_id: string; new_decision_id: string } | null;
};
export type Expert = {
  person_id: string; name: string; activity: number; authored: number; reviewed: number;
  normalised_activity: number; pagerank: number; betweenness: number; knowledge_bridge: boolean; score: number; bus_factor_warning: boolean;
};
export type BusFactor = { system_id: string; experts: { id: string; name: string; activity: number }[] };
export type TimelineRow = {
  task_id: string; kind: string; status: string; created_by: string | null; created_at: number;
  handoffs: { agent: string; ts: number }[];
};
export type IngestResult = {
  status: string; decision_id?: string; supersedes_id?: string | null; stale_items?: number; docs?: number; tickets?: number; reason?: string;
  extraction?: { summary: string; rationale: string; new_claim: string };
};
export type DocCheck = {
  claim_id: string; claim_text: string; quote: string; in_force: boolean;
  closed_by: string | null; closed_by_summary: string | null; closed_at: number | null; closed_by_name: string | null;
};
export type DocIngestResult = { status: string; doc_id: string; task_id: string; extraction: { system_id: string | null }; checks: DocCheck[]; conflicts: number; tasks: InboxItem[] };
export type DriftRow = {
  item_id: string; item_label: string; title: string; how: string; stale_text: string; decision_id: string; decision_summary: string;
  decided_at: number; task_id: string | null; task_status: string | null; owner_id: string | null; owner_name: string | null; routed_via: string;
};
export type Health = {
  health: number; items: number; docs: number; open_tickets: number; stale_items: number; untracked_stale: number;
  decisions: number; in_force: number; unevidenced: number; messages: number; prs: number; chunks: number; people: number;
  drift: DriftRow[]; unowned: { id: string; label: string; title: string }[];
  bus_factor: BusFactor[]; bridges: { person_id: string; name: string; score: number }[];
};
export type SessionChange = { system_id: string; question: string; last_asked: number; summary: string; changed_at: number; now_in_force: string };

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API}${path}`, { ...init, headers: { "Content-Type": "application/json" } });
  if (!r.ok) throw new Error(`${path}: ${r.status} ${await r.text()}`);
  return r.json();
}
const post = <T,>(path: string, body: unknown) => req<T>(path, { method: "POST", body: JSON.stringify(body) });

export const api = {
  ask: (question: string, session_id: string, as_of?: number, record = true) => post<Answer>("/ask", { question, session_id, as_of: as_of ?? null, record }),
  startSession: () => post<{ session_id: string; changes: SessionChange[] }>("/session/start", {}),
  ingest: (channel: string, author: string, text: string) => post<IngestResult>("/ingest", { channel, author, text }),
  ingestDoc: (title: string, author: string, text: string) => post<DocIngestResult>("/ingest/doc", { title, author, text }),
  health: () => req<Health>("/knowledge-health"),
  dispatchAudit: () => post<{ created: number }>("/audit/dispatch", {}),
  inbox: () => req<InboxItem[]>("/inbox"),
  approve: (id: string) => post<{ new_version_id: string }>(`/tasks/${encodeURIComponent(id)}/approve`, {}),
  reject: (id: string) => post<unknown>(`/tasks/${encodeURIComponent(id)}/reject`, {}),
  timeline: () => req<TimelineRow[]>("/agents/timeline"),
  whoKnows: (system: string) => req<Expert[]>(`/who-knows/${system}`),
  busFactor: () => req<BusFactor[]>("/bus-factor"),
  informal: () => req<{ community: number; members: string[] }[]>("/informal-teams"),
  graph: () => req<GraphEdge[]>("/graph"),
  systems: () => req<string[]>("/systems"),
  reset: () => post<unknown>("/demo/reset", {}),
};

export const fmtDate = (ms: number) =>
  new Date(ms).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
export const fmtTime = (ms: number) =>
  new Date(ms).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
