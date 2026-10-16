"""Strata MCP server: lets Claude Desktop, Cursor or any MCP client query the company brain.

Four read-only tools, each a thin wrapper over the same graph queries the web app uses:
  why          decision in force, lineage and evidence for a question
  who_knows    ranked expertise for a system (activity x PageRank, betweenness badge, bus-factor warning)
  whats_stale  docs and tickets that assert closed knowledge, with owners and drafted fixes
  as_of        the decision in force for a system on a given date

The tools never write: approving a fix stays a human click in the web app. No tool calls an LLM.
Run over stdio:  python mcp_server.py
"""
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.chdir(Path(__file__).parent)  # .env and relative paths resolve wherever the MCP client launches us

import brain  # noqa: E402
from agents import concierge  # noqa: E402
from graph.service import GraphService  # noqa: E402
from mcp.server.mcpserver import MCPServer  # noqa: E402

mcp = MCPServer(
    "strata",
    instructions=(
        "Strata is a company brain over a FalkorDB graph of decisions, docs, tickets, chats and people. "
        "Use `why` for the reasoning behind a decision, `as_of` for what was true on a date, `who_knows` for "
        "expertise and bus-factor risk, and `whats_stale` for documents that contradict current decisions. "
        "Every answer lists its sources; if there is no evidence the tools say so instead of guessing."
    ),
)
_svc: GraphService | None = None


def _graph() -> GraphService:
    global _svc
    if _svc is None:
        _svc = GraphService()
    return _svc


def _ms(date: str) -> int:
    """'2026-04-15' or '2026-04-15T09:30' (UTC) -> epoch milliseconds."""
    try:
        d = datetime.fromisoformat(date.strip())
    except ValueError as e:
        raise ValueError(f"expected an ISO date like 2026-04-15, got {date!r}") from e
    return int((d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp() * 1000)


def _iso(ms: int | None) -> str | None:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d") if ms else None


def _unknown(what: str, **extra: Any) -> dict[str, Any]:
    return {"found": False, "message": f"I don't know. {what}", **extra}


@mcp.tool()
def why(question: str, as_of: str | None = None) -> dict[str, Any]:
    """Explain why something is the way it is: the decision in force, who made it, what it replaced, and the evidence.

    Args:
        question: natural language, e.g. "Why do we use Postgres for sessions?"
        as_of: optional ISO date (UTC) to answer as the company knew it then, e.g. "2026-04-15"
    """
    t = _ms(as_of) if as_of else None
    a = concierge.answer(_graph(), question, t, intent="why")
    return {
        "found": a.found,
        "answer": a.text,
        "as_of": _iso(a.as_of),
        "sentences": [s.model_dump() for s in a.segments],
        "sources": a.sources,
        "path": a.path,
        "searched": a.searched,
    }


@mcp.tool()
def who_knows(system: str, top: int = 5) -> dict[str, Any]:
    """Who actually knows a system, from authored and reviewed work (not the org chart).

    Score = normalised activity x (1 + PageRank over collaboration). Includes a knowledge-bridge flag
    (betweenness) and a bus-factor warning when only one person has meaningful activity.

    Args:
        system: a system id or name, e.g. "billing-reconciler" or "billing reconciler"
        top: how many people to return
    """
    g = _graph()
    sid = concierge.resolve_system(g, system)
    if sid is None:
        return _unknown(f"No system matches {system!r}.", systems=[s["id"] for s in g.run("systems")])
    ranked = brain.who_knows(g, sid)
    if not ranked:
        return _unknown(f"Nobody has authored or reviewed work about {sid}.", system=sid)
    work = g.run("person_work", person_id=ranked[0]["person_id"], system_id=sid)
    return {
        "found": True,
        "system": sid,
        "bus_factor_warning": ranked[0]["bus_factor_warning"],
        "experts": [
            {"person_id": r["person_id"], "name": r["name"], "score": r["score"], "authored": int(r["authored"]),
             "reviewed": int(r["reviewed"]), "pagerank": r["pagerank"], "betweenness": r["betweenness"],
             "knowledge_bridge": r["knowledge_bridge"]}
            for r in ranked[: max(1, top)]
        ],
        "sources_for_top_expert": [{"id": w["id"], "kind": w["kind"], "text": w["text"], "url": w["url"]} for w in work],
    }


@mcp.tool()
def whats_stale(decision_id: str | None = None) -> dict[str, Any]:
    """Docs and open tickets that assert knowledge a decision has closed, with accountable owner and drafted fix.

    Without arguments: the open items in the Drift Inbox (awaiting human approval).
    With `decision_id`: what that decision made stale (read-only), e.g. "D-02".
    """
    g = _graph()
    if decision_id:
        if not g.run("decisions_by_ids", ids=[decision_id]):
            return _unknown(f"There is no decision {decision_id!r}.")
        names = {p["id"]: p["name"] for p in g.run("people")}
        items = [{"item_id": i["item_id"], "kind": i["item_label"], "title": i["title"], "how": i["how"],
                  "stale_statement": i["stale_text"], "owner": names[i["owner_id"]], "routed_via": i["routed_via"]}
                 for i in brain.whats_stale(g, decision_id)]
        return {"found": bool(items), "decision_id": decision_id, "count": len(items), "items": items}
    rows = [r for r in g.run("inbox") if r["status"] == "open"]
    items = []
    for r in rows:
        why_stale = (g.run("stale_reason", task_id=r["task_id"]) or [{}])[0]
        items.append({"task_id": r["task_id"], "item_id": r["item_id"], "kind": r["item_label"], "title": r["item_title"],
                      "owner": r["owner_name"], "caused_by": r["decision_summary"], "stale_statement": why_stale.get("stale_text"),
                      "drafted_fix": r["draft"]})
    return {"found": bool(items), "count": len(items), "items": items,
            "note": "Fixes are drafts. Approving them is a human action in the web app."}


@mcp.tool()
def as_of(system: str, date: str) -> dict[str, Any]:
    """The decision in force for a system on a given date, with lineage and evidence (time travel).

    Args:
        system: a system id or name, e.g. "session-store" or "event bus"
        date: ISO date (UTC), e.g. "2026-04-15"
    """
    g = _graph()
    sid = concierge.resolve_system(g, system)
    if sid is None:
        return _unknown(f"No system matches {system!r}.", systems=[s["id"] for s in g.run("systems")])
    r = brain.why(g, sid, _ms(date))
    if not r:
        return _unknown(f"No decision about {sid} was in force on {date}.", system=sid)
    older = {d["id"]: d for d in g.run("decisions_by_ids", ids=sorted({i for c in r["lineage"] for i in c} - {r["decision_id"]}))} if r["lineage"] else {}
    return {
        "found": True,
        "system": sid,
        "date": date,
        "decision": {"id": r["decision_id"], "summary": r["summary"], "rationale": r["rationale"],
                     "decided_by": r["decided_by_name"], "valid_from": _iso(r["valid_from"]), "valid_to": _iso(r["valid_to"])},
        "replaced": [{"id": o["id"], "summary": o["summary"], "valid_from": _iso(o["valid_from"]), "valid_to": _iso(o["valid_to"])} for o in older.values()],
        "later_superseded_by": [{"id": s["id"], "summary": s["summary"], "valid_from": _iso(s["valid_from"])} for s in r["superseded_by"]],
        "evidence": r["evidence"],
    }


if __name__ == "__main__":
    mcp.run()
