"use client";
import { useEffect, useRef, useState } from "react";
import { api, fmtDate, type Answer } from "@/lib/api";

type Msg = { role: "user"; text: string } | { role: "assistant"; answer: Answer; rerun: boolean };

const SUGGESTIONS = [
  "Why do we use Postgres for sessions?",
  "Why did we use Redis for sessions? (as of April)",
  "How do we deploy?",
  "Who owns the onboarding doc?",
  "Who knows the billing reconciler?",
  "What changed since June?",
  "What does Aisha work on?",
  "Which docs are out of date?",
];

export default function Chat(props: {
  sessionId: string; asOf: number | null; onAnswer: (a: Answer) => void; onSelectSource: (id: string, a: Answer) => void;
}) {
  const { sessionId, asOf, onAnswer, onSelectSource } = props;
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const last = useRef<{ q: string; tool: string } | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const first = useRef(true);

  const run = async (q: string, as_of: number | undefined, rerun: boolean) => {
    setBusy(true);
    if (!rerun) setMsgs((m) => [...m, { role: "user", text: q }]);
    try {
      const a = await api.ask(q, sessionId, as_of, !rerun);
      last.current = { q, tool: a.tool };
      setMsgs((m) => [...m, { role: "assistant", answer: a, rerun }]);
      onAnswer(a);
    } catch (e) {
      setMsgs((m) => [...m, { role: "assistant", rerun, answer: errAnswer(q, String(e)) }]);
    } finally { setBusy(false); }
  };

  // Moving the time slider re-asks the last "why" question as of that time.
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    if (!last.current || last.current.tool !== "why") return;
    const t = setTimeout(() => run(last.current!.q.replace(/\s*\(as of \w+\)/i, ""), asOf ?? undefined, true), 500);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [asOf]);

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, busy]);

  const send = (q: string) => { if (q.trim() && !busy) { setInput(""); run(q.trim(), asOf ?? undefined, false); } };

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
        {msgs.length === 0 && (
          <div>
            <div className="mb-1 text-sm font-medium">Ask the company brain</div>
            <div className="mb-3 text-xs text-mute">Every answer shows the graph path it used and cites its sources. No evidence means “I don’t know”.</div>
            <div className="flex flex-col gap-2">
              {SUGGESTIONS.map((s) => (
                <button key={s} className="card px-3 py-2 text-left text-sm text-ink hover:border-accent" onClick={() => send(s)}>{s}</button>
              ))}
            </div>
          </div>
        )}
        {msgs.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="ml-8 rounded-lg bg-raised px-3 py-2 text-sm">{m.text}</div>
          ) : (
            <AnswerView key={i} a={m.answer} rerun={m.rerun} onSource={(id) => onSelectSource(id, m.answer)} onPath={() => onAnswer(m.answer)} />
          ),
        )}
        {busy && <div className="pulse text-xs text-mute">Searching the graph…</div>}
        <div ref={bottom} />
      </div>
      <form className="flex gap-2 border-t border-line p-3" onSubmit={(e) => { e.preventDefault(); send(input); }}>
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Why… / Who owns… / How do we… / What changed?"
          className="flex-1 rounded-md border border-line bg-raised px-3 py-2 text-sm outline-none focus:border-accent" />
        <button className="btn-accent" disabled={busy || !input.trim()}>Ask</button>
      </form>
    </div>
  );
}

const errAnswer = (q: string, e: string): Answer => ({
  question: q, tool: "error", found: false, text: `Backend error: ${e}`, segments: [{ text: `Backend error: ${e}`, sources: [] }],
  path: { nodes: [], edges: [] }, sources: [], searched: [], as_of: Date.now(),
});

function AnswerView({ a, rerun, onSource, onPath }: { a: Answer; rerun: boolean; onSource: (id: string) => void; onPath: () => void }) {
  const idx = new Map(a.sources.map((s, i) => [s.id, i + 1]));
  return (
    <div className={`card p-3 text-sm ${a.found ? "" : "border-dashed"}`}>
      {rerun && <div className="mb-1 text-[11px] text-accent">↺ re-run as of {fmtDate(a.as_of)}</div>}
      <div className="space-y-1.5 leading-relaxed">
        {a.segments.map((s, i) => (
          <p key={i} className={!a.found ? "text-mute" : s.tone === "warning" ? "rounded-md border-l-2 border-stale bg-stale/10 py-1 pl-2 text-stale" : ""}>
            {s.tone === "warning" && <span className="mr-1">⚠</span>}{s.text}
            {s.sources.filter((id) => idx.has(id)).map((id) => (
              <button key={id} onClick={() => onSource(id)} title={a.sources.find((x) => x.id === id)?.text}
                className="ml-1 align-super text-[10px] font-medium text-accent hover:underline">[{idx.get(id)}]</button>
            ))}
          </p>
        ))}
      </div>
      {!a.found && a.searched.length > 0 && (
        <div className="mt-2 rounded-md bg-raised p-2 text-[11px] text-mute">
          <div className="mb-1 font-medium">What I searched</div>
          {a.searched.map((s, i) => <div key={i} className="font-mono">{s}</div>)}
        </div>
      )}
      {a.found && a.sources.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {a.sources.map((s, i) => (
            <button key={s.id} className="chip hover:border-accent hover:text-ink" onClick={() => onSource(s.id)}>
              [{i + 1}] {s.kind} · {s.id}
            </button>
          ))}
        </div>
      )}
      <div className="mt-2 flex items-center gap-2 text-[11px] text-mute">
        <span className="chip">tool: {a.tool}</span>
        {a.path.nodes.length > 0 && <button className="text-accent hover:underline" onClick={onPath}>show path in graph ({a.path.nodes.length} nodes)</button>}
      </div>
    </div>
  );
}
