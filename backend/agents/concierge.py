"""Concierge agent: answers questions by choosing a graph tool and composing a sourced answer.

Routing is hybrid: fast deterministic matching (system names, then vector retrieval over chunks), with
an LLM router only when the intent is unclear. The LLM never writes Cypher and never writes the answer
text: each sentence is composed from graph results and carries the ids of its evidence.
"""
import re
import time
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel

import brain
import llm
from embeddings import embed
from graph.service import GraphService

MAX_VECTOR_DISTANCE = 0.55  # cosine distance above which retrieval is treated as "nothing relevant"
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
GENERIC = {"service", "the", "and"}


class Segment(BaseModel):
    text: str
    sources: list[str] = []


class Answer(BaseModel):
    question: str
    tool: str
    found: bool
    text: str
    segments: list[Segment]
    path: dict[str, Any]  # {"nodes": [ids], "edges": [[src, type, dst]], "labels": {id: display name}}
    sources: list[dict[str, Any]]
    searched: list[str] = []
    as_of: int
    shown_decision: dict[str, Any] | None = None


class Route(BaseModel):
    tool: Literal["why", "who_knows", "whats_stale", "bus_factor", "bridges", "unknown"]
    system_id: str | None = None


def _d(ms: int | None) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%b %d, %Y") if ms else "now"


def parse_as_of(question: str, now: int) -> int:
    """'as of April' -> mid-April of the current year; otherwise now."""
    m = re.search(r"as of (\w+)", question.lower())
    if m and m.group(1) in MONTHS:
        year = datetime.fromtimestamp(now / 1000, tz=timezone.utc).year
        return int(datetime(year, MONTHS.index(m.group(1)) + 1, 15, tzinfo=timezone.utc).timestamp() * 1000)
    return now


def _stem(w: str) -> str:
    return w[:-1] if w.endswith("s") and len(w) > 3 else w


def _tokens(text: str) -> set[str]:
    return {_stem(t) for t in re.findall(r"[a-z0-9]+", text.lower())} - GENERIC


def _system_by_name(svc: GraphService, question: str) -> str | None:
    qt = _tokens(question)
    scored = sorted(((len(_tokens(s["id"].replace("-", " ")) & qt), s["id"]) for s in svc.run("systems")), reverse=True)
    if scored[0][0] >= 1 and (len(scored) == 1 or scored[0][0] > scored[1][0]):
        return scored[0][1]
    return None


def resolve_system(svc: GraphService, text: str) -> str | None:
    """A system id from free text: exact id or name tokens (no LLM, no vector search)."""
    ids = {x["id"] for x in svc.run("systems")}
    return text if text in ids else _system_by_name(svc, text)


def _entry_points(svc: GraphService, question: str) -> tuple[str | None, list[str]]:
    """Q1: vector retrieval; the system most retrieved chunks are about, plus a trace of what was searched."""
    hits = svc.run("find_entry_points_vector", qvec=embed([question])[0])
    searched = [f"{h['src_id']} (distance {h['score']:.2f})" for h in hits[:5]]
    near = [h for h in hits if h["score"] <= MAX_VECTOR_DISTANCE]
    if not near:
        return None, searched
    links = svc.run("systems_of_sources", ids=[h["src_id"] for h in near])
    votes: dict[str, float] = {}
    for link in links:
        best = min(h["score"] for h in near if h["src_id"] == link["src_id"])
        votes[link["system_id"]] = votes.get(link["system_id"], 0) + (1 - best)
    return (max(votes, key=votes.get) if votes else None), searched


def _intent(question: str) -> str | None:
    q = question.lower()
    if re.search(r"stale|outdated|out of date|drift|contradict", q):
        return "whats_stale"
    if re.search(r"bus factor|single point|only one person", q):
        return "bus_factor"
    if re.search(r"\bconnects?\b|\bbridges?\b", q):
        return "bridges"
    if re.search(r"who (knows|owns|understands)|expert", q):
        return "who_knows"
    if re.search(r"\bwhy\b|decid|reason|how come", q):
        return "why"
    return None


def _idk(question: str, tool: str, searched: list[str], now: int, note: str) -> Answer:
    text = f"I don't know. {note}"
    return Answer(question=question, tool=tool, found=False, text=text, segments=[Segment(text=text)],
                  path={"nodes": [], "edges": []}, sources=[], searched=searched, as_of=now)


def _src(e: dict[str, Any]) -> dict[str, Any]:
    return {"id": e["id"], "kind": e["kind"], "text": e["text"], "url": e.get("url")}


def _answer_why(svc: GraphService, question: str, system_id: str, as_of: int, searched: list[str]) -> Answer:
    r = brain.why(svc, system_id, as_of)
    if not r:
        return _idk(question, "why", searched + [f"decisions about {system_id} as of {_d(as_of)}"], as_of,
                    f"I found no decision about {system_id} in force on {_d(as_of)}.")
    ev_ids = [e["id"] for e in r["evidence"]]
    nodes = [system_id, r["decision_id"]]
    edges: list[list[str]] = [[r["decision_id"], "AFFECTS", system_id]]
    sources = {e["id"]: _src(e) for e in r["evidence"]}
    segs = [Segment(text=f"As of {_d(as_of)}, the decision in force for {system_id} is: {r['summary']}.", sources=ev_ids)]
    if r["decided_by"]:
        nodes.append(r["decided_by"]); edges.append([r["decision_id"], "DECIDED_BY", r["decided_by"]])
        segs.append(Segment(text=f"It was made by {r['decided_by_name']} on {_d(r['valid_from'])}.", sources=ev_ids))
    if r["rationale"]:
        segs.append(Segment(text=f"Rationale: {r['rationale']}", sources=ev_ids))
    for eid in ev_ids:
        nodes.append(eid); edges.append([r["decision_id"], "EVIDENCED_BY", eid])
    chain_ids = sorted({i for chain in r["lineage"] for i in chain} - {r["decision_id"]})
    older = {d["id"]: d for d in svc.run("decisions_by_ids", ids=chain_ids)} if chain_ids else {}
    for chain in r["lineage"]:
        for a, b in zip(chain, chain[1:]):
            edges.append([a, "SUPERSEDES", b]); nodes.append(b)
    for oid in chain_ids:
        o = older[oid]
        oev = [e["id"] for e in o["evidence"]]
        for e in o["evidence"]:
            sources[e["id"]] = _src(e); nodes.append(e["id"]); edges.append([oid, "EVIDENCED_BY", e["id"]])
        segs.append(Segment(text=f"It replaced: {o['summary']} (decided {_d(o['valid_from'])} by {o['decided_by_name']}, closed {_d(o['valid_to'])}).", sources=oev))
    if r["superseded_by"]:
        nw = svc.run("decisions_by_ids", ids=[r["superseded_by"][0]["id"]])[0]
        for e in nw["evidence"]:
            sources[e["id"]] = _src(e)
        edges.append([nw["id"], "SUPERSEDES", r["decision_id"]]); nodes.append(nw["id"])
        segs.append(Segment(text=f"Note: this was later superseded on {_d(nw['valid_from'])} by: {nw['summary']}.",
                            sources=[e["id"] for e in nw["evidence"]]))
    return Answer(question=question, tool="why", found=True, text=" ".join(s.text for s in segs), segments=segs,
                  path={"nodes": list(dict.fromkeys(nodes)), "edges": edges}, sources=list(sources.values()),
                  searched=searched, as_of=as_of,
                  shown_decision={"decision_id": r["decision_id"], "system_id": system_id, "valid_from": r["valid_from"]})


def _answer_who(svc: GraphService, question: str, system_id: str, now: int, searched: list[str]) -> Answer:
    ranked = brain.who_knows(svc, system_id)
    if not ranked:
        return _idk(question, "who_knows", searched, now, f"Nobody has authored or reviewed work about {system_id}.")
    top = ranked[0]
    work = svc.run("person_work", person_id=top["person_id"], system_id=system_id)
    src = [{"id": w["id"], "kind": w["kind"], "text": w["text"], "url": w["url"]} for w in work]
    src_ids = [w["id"] for w in work]
    segs = [Segment(text=f"{top['name']} knows {system_id} best (score {top['score']}): {int(top['authored'])} authored and "
                         f"{int(top['reviewed'])} reviewed items, PageRank {top['pagerank']:.3f}.", sources=src_ids)]
    for p in ranked[1:4]:
        segs.append(Segment(text=f"Then {p['name']} (score {p['score']}, {p['activity']} items)."))
    if top["bus_factor_warning"]:
        segs.append(Segment(text=f"Bus-factor warning: {top['name']} is the only person with meaningful activity on {system_id}.", sources=src_ids))
    if top["knowledge_bridge"]:
        segs.append(Segment(text=f"{top['name']} is also a knowledge bridge (betweenness {top['betweenness']:.1f}).", sources=[]))
    nodes = [system_id] + [p["person_id"] for p in ranked[:4]]
    edges = [[p["person_id"], "EXPERT_ON", system_id] for p in ranked[:4]]
    return Answer(question=question, tool="who_knows", found=True, text=" ".join(s.text for s in segs), segments=segs,
                  path={"nodes": nodes, "edges": edges, "labels": {p["person_id"]: p["name"] for p in ranked[:4]}},
                  sources=src, searched=searched, as_of=now)


def _answer_bus(svc: GraphService, question: str, now: int) -> Answer:
    rows = brain.bus_factor(svc)
    segs = [Segment(text=f"{r['system_id']} is understood by only {r['experts'][0]['name']} ({r['experts'][0]['activity']} items).") for r in rows]
    if not segs:
        return _idk(question, "bus_factor", [], now, "No system currently has a single point of knowledge.")
    return Answer(question=question, tool="bus_factor", found=True, text=" ".join(s.text for s in segs), segments=segs,
                  path={"nodes": [r["system_id"] for r in rows] + [r["experts"][0]["id"] for r in rows],
                        "edges": [[r["experts"][0]["id"], "EXPERT_ON", r["system_id"]] for r in rows],
                        "labels": {r["experts"][0]["id"]: r["experts"][0]["name"] for r in rows}},
                  sources=[], searched=[], as_of=now)


def _answer_bridge(svc: GraphService, question: str, now: int) -> Answer:
    teams = [t for t in ("Platform", "Payments", "Growth", "Data", "Mobile") if t.lower() in question.lower()]
    for cand in svc.run("betweenness")[:6]:
        own = svc.run("team_of", person_id=cand["person_id"])[0]["team"]
        reach = {r["team"] for r in svc.run("person_collab_teams", person_id=cand["person_id"])} | {own}
        if set(teams) <= reach:
            names = {p["id"]: p["name"] for p in svc.run("people")}
            others = sorted(reach)
            text = (f"{names[cand['person_id']]} ({own}) connects {', '.join(others)}: betweenness {cand['score']:.1f}, "
                    f"the highest of anyone linking these groups.")
            seg = Segment(text=text, sources=[])
            return Answer(question=question, tool="bridges", found=True, text=text, segments=[seg],
                          path={"nodes": [cand["person_id"]], "edges": [], "labels": {cand["person_id"]: names[cand["person_id"]]}}, sources=[], searched=[], as_of=now)
    return _idk(question, "bridges", [], now, "No one connects those teams in the collaboration graph.")


def _answer_stale(svc: GraphService, question: str, now: int) -> Answer:
    rows = [r for r in svc.run("inbox") if r["status"] == "open"]
    if not rows:
        return _idk(question, "whats_stale", ["open drift tasks"], now, "Nothing is currently flagged as stale.")
    segs = [Segment(text=f"{r['item_label']} \"{r['item_title']}\" is stale after: {r['decision_summary']}. Owner: {r['owner_name']}.",
                    sources=[r["item_id"]]) for r in rows]
    return Answer(question=question, tool="whats_stale", found=True, text=" ".join(s.text for s in segs), segments=segs,
                  path={"nodes": list({x for r in rows for x in (r["item_id"], r["decision_id"], r["owner_id"])}),
                        "edges": [[r["item_id"], "STALE_AFTER", r["decision_id"]] for r in rows]},
                  sources=[{"id": r["item_id"], "kind": r["item_label"], "text": r["item_title"], "url": None} for r in rows],
                  searched=[], as_of=now)


def answer(svc: GraphService, question: str, as_of: int | None = None, intent: str | None = None) -> Answer:
    """`intent` skips intent detection (and the LLM router): the MCP tools already know which tool they are."""
    now = int(time.time() * 1000)
    t = as_of or parse_as_of(question, now)
    intent = intent or _intent(question)
    searched: list[str] = []
    system_id = _system_by_name(svc, question)
    if intent is None:  # unclear: let the LLM pick a tool from the vetted list
        route = llm.structured(
            f"Pick the tool for this question. Tools: why (a decision and its history), who_knows (expertise), "
            f"whats_stale, bus_factor, bridges, unknown.\nSystems: {[s['id'] for s in svc.run('systems')]}\nQuestion: {question}",
            Route)
        intent, system_id = route.tool, system_id or route.system_id
        searched.append(f"LLM router chose: {route.tool}")
        if intent == "unknown":
            return _idk(question, "unknown", searched, t, "That is not a question I can answer from the company graph.")
    if intent == "whats_stale":
        return _answer_stale(svc, question, now)
    if intent == "bus_factor":
        return _answer_bus(svc, question, now)
    if intent == "bridges":
        return _answer_bridge(svc, question, now)
    if system_id is None:
        system_id, trace = _entry_points(svc, question)
        searched += trace
    if system_id is None:
        return _idk(question, intent, searched, t, "I searched documents and messages and found nothing relevant to that question.")
    searched.append(f"system resolved: {system_id}")
    if intent == "who_knows":
        return _answer_who(svc, question, system_id, now, searched)
    ans = _answer_why(svc, question, system_id, t, searched)
    if t < now - 60_000:  # a historical view is not what the user was "shown as current", so it is not remembered
        ans.shown_decision = None
    return ans
