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
    tone: Literal["normal", "warning"] = "normal"  # "warning": the graph says this source is out of date


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
    tool: Literal["why", "who_knows", "owner", "person", "whats_changed", "search", "whats_stale", "bus_factor", "bridges", "unknown"]
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


def parse_since(question: str, until: int) -> tuple[int, str]:
    """'last week' / 'last 3 days' / 'since June' / 'recently' -> (start of the window, how to say it). Default: 30 days."""
    q, day = question.lower(), 86_400_000
    if m := re.search(r"(?:last|past) (\d+) days?", q):
        return until - int(m.group(1)) * day, f"in the last {m.group(1)} days"
    if m := re.search(r"since (\w+)", q):
        if m.group(1) in MONTHS:
            now = datetime.fromtimestamp(until / 1000, tz=timezone.utc)
            month = MONTHS.index(m.group(1)) + 1
            year = now.year if month <= now.month else now.year - 1
            start = int(datetime(year, month, 1, tzinfo=timezone.utc).timestamp() * 1000)
            return start, f"since {_d(start)}"
    if re.search(r"\btoday\b|\byesterday\b|24 hours", q):
        return until - 2 * day, "in the last 2 days"
    if re.search(r"\bweek\b", q):
        return until - 7 * day, "in the last 7 days"
    if re.search(r"\bquarter\b", q):
        return until - 90 * day, "in the last 90 days"
    return until - 30 * day, "in the last 30 days"


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
    if re.search(r"stale|outdated|out of date|drift|contradict|(docs?|tickets?|pages?) (are|is) wrong|no longer true", q):
        return "whats_stale"
    if re.search(r"what('s| has| have)? (changed|new)|what changed|recent (changes|decisions)|changelog|\bchanges? (since|in the|this|last)", q):
        return "whats_changed"
    if re.search(r"bus factor|single point|only one person", q):
        return "bus_factor"
    if re.search(r"\bconnects?\b|\bbridges?\b", q):
        return "bridges"
    if re.search(r"who (owns|maintains|is responsible|is accountable)|\bowner of\b|who should (fix|update)", q):
        return "owner"
    if re.search(r"who (knows|understands|can help|should review|should i ask)|expert", q):
        return "who_knows"
    if re.search(r"\bwork(s|ing)? on\b|\bwho is \w+|tell me about \w+|what does \w+ (do|own)\b", q):
        return "person"
    if re.search(r"\bwhy\b|decid|reason|how come", q):
        return "why"
    if re.search(r"^\s*(how|where)\b|\bhow (do|does|to|should|can|are) (we|i|you)\b|\bwhat('s| is| are) the (process|procedure|steps|command)", q):
        return "search"
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
    """Everything that contradicts a newer decision (the audit), not only items already in the Drift Inbox."""
    rows = brain.drift_audit(svc)
    if not rows:
        return _idk(question, "whats_stale", ["docs and open tickets asserting closed claims or citing superseded decisions"], now,
                    "No doc or open ticket contradicts a decision in force.")
    tracked = {"open": "fix awaiting approval", "approved": "fixed", "rejected": "fix rejected, still wrong"}
    segs = [Segment(text=f"{len({r['item_id'] for r in rows})} items state something that is no longer true.")]
    for r in rows:
        status = tracked.get(r["task_status"], "not yet in the Drift Inbox")
        segs.append(Segment(text=f"{r['item_label']} \"{r['title']}\" still says \"{r['stale_text']}\", but on {_d(r['decided_at'])}: "
                                 f"{r['decision_summary']}. Owner: {r['owner_name']} ({status}).", sources=[r["item_id"]], tone="warning"))
    edges = [[r["item_id"], "STALE_AFTER", r["decision_id"]] for r in rows]
    return Answer(question=question, tool="whats_stale", found=True, text=" ".join(s.text for s in segs), segments=segs,
                  path={"nodes": list(dict.fromkeys(x for r in rows for x in (r["item_id"], r["decision_id"]))), "edges": edges},
                  sources=[{"id": r["item_id"], "kind": r["item_label"], "text": r["title"], "url": None} for r in rows],
                  searched=[], as_of=now)


def _answer_changes(svc: GraphService, question: str, until: int) -> Answer:
    since, window = parse_since(question, until)
    rows = svc.run("changes_since", since=since, until=until)
    if not rows:
        last = svc.run("changes_since", since=0, until=until)
        note = f"No decision changed {window} (since {_d(since)})."
        if last:
            note += f" The most recent change was on {_d(last[0]['valid_from'])}: {last[0]['summary']} ({last[0]['system_id']})."
        return _idk(question, "whats_changed", [f"decisions with valid_from between {_d(since)} and {_d(until)}"], until, note)
    sources: dict[str, dict[str, Any]] = {}
    span = window if window.startswith("since") else f"{window} (since {_d(since)})"
    segs = [Segment(text=f"{len(rows)} decision{'s' * (len(rows) != 1)} changed {span}.")]
    nodes: list[str] = []
    edges: list[list[str]] = []
    for r in rows:
        ev = [e for e in r["evidence"] if e.get("id")]
        sources.update({e["id"]: _src(e) for e in ev})
        text = f"{_d(r['valid_from'])} · {r['system_id']}: {r['summary']}, decided by {r['decided_by_name']}."
        if r["replaced_id"]:
            text += f" It replaced: {r['replaced_summary']}."
            edges.append([r["decision_id"], "SUPERSEDES", r["replaced_id"]]); nodes.append(r["replaced_id"])
        if r["valid_to"]:
            text += f" (Itself superseded on {_d(r['valid_to'])}.)"
        segs.append(Segment(text=text, sources=[e["id"] for e in ev]))
        nodes += [r["decision_id"], r["system_id"]]; edges.append([r["decision_id"], "AFFECTS", r["system_id"]])
    drift = svc.run("drift_since", since=since, until=until)
    if drift:
        by = {k: sum(d["status"] == k for d in drift) for k in ("open", "approved", "rejected")}
        segs.append(Segment(text=f"Knowledge that went stale because of this: {len(drift)} items "
                                 f"({by['approved']} fixed, {by['open']} awaiting approval, {by['rejected']} rejected).",
                            sources=[d["item_id"] for d in drift]))
        sources.update({d["item_id"]: {"id": d["item_id"], "kind": d["item_label"], "text": d["item_title"], "url": None} for d in drift})
    return Answer(question=question, tool="whats_changed", found=True, text=" ".join(s.text for s in segs), segments=segs,
                  path={"nodes": list(dict.fromkeys(nodes)), "edges": edges}, sources=list(sources.values()),
                  searched=[f"decisions with valid_from between {_d(since)} and {_d(until)}"], as_of=until)


STOP = {"who", "own", "owner", "the", "doc", "document", "page", "ticket", "is", "of", "for", "a", "an", "what", "doe", "do",
        "responsible", "maintain", "maintains", "accountable", "our", "we", "should", "fix", "update", "to", "on", "about"}


def _match_items(svc: GraphService, question: str) -> list[dict[str, Any]]:
    """Docs/tickets whose title shares a distinctive (non-system-name) word with the question; best matches only."""
    sys_tokens = {t for s in svc.run("systems") for t in _tokens(s["id"].replace("-", " "))}
    q = _tokens(question) - STOP
    scored = []
    for it in svc.run("current_items"):
        tt = _tokens(it["title"] or "") - STOP
        distinctive = len((q - sys_tokens) & (tt - sys_tokens))
        if distinctive:
            scored.append((distinctive * 10 + len(q & tt), it))
    if not scored:
        return []
    best = max(sc for sc, _ in scored)
    return [it for sc, it in scored if sc == best][:3]


def _stale_notes(svc: GraphService, ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for f in svc.run("stale_flags", ids=ids) if ids else []:
        out.setdefault(f["src_id"], []).append(f)
    return out


def _warning(f: dict[str, Any], kind: str) -> str:
    said = {"ASSERTS": "says", "CITES": "cites", "EVIDENCE_FOR": "records the decision"}.get(f["how"], "says")
    text = f"Out of date: this {kind.lower()} {said} \"{f['stale_text']}\""
    text += f", but on {_d(f['new_from'])}: {f['new_summary']} ({f['new_id']})." if f["new_id"] else ", which is no longer in force."
    if f.get("newer_version"):
        text += f" An approved newer version exists: {f['newer_version']}."
    return text


def _answer_owner(svc: GraphService, question: str, now: int) -> Answer:
    names = {p["id"]: p["name"] for p in svc.run("people")}
    items = _match_items(svc, question)
    if items:
        segs, nodes, edges, sources = [], [], [], []
        notes = _stale_notes(svc, [i["id"] for i in items])
        for it in items:
            o = brain.owner_of(svc, it["id"])
            how = "owns it directly" if o["routed_via"] == "direct owner" else f"is accountable for it ({o['routed_via']}; nobody owns it directly)"
            segs.append(Segment(text=f"{it['label']} \"{it['title']}\": {names.get(o['owner_id'], 'nobody')} {how}.", sources=[it["id"]]))
            for f in notes.get(it["id"], []):
                segs.append(Segment(text=_warning(f, it["label"]), sources=[it["id"]], tone="warning"))
            sources.append({"id": it["id"], "kind": it["label"], "text": it["title"], "url": it["url"]})
            if o["owner_id"]:
                nodes += [o["owner_id"], it["id"]]; edges.append([o["owner_id"], "OWNS", it["id"]])
        return Answer(question=question, tool="owner", found=True, text=" ".join(s.text for s in segs), segments=segs,
                      path={"nodes": list(dict.fromkeys(nodes)), "edges": edges, "labels": {n: names[n] for n in nodes if n in names}},
                      sources=sources, searched=[f"doc/ticket titles matching: {', '.join(i['id'] for i in items)}"], as_of=now)
    system_id = _system_by_name(svc, question)
    if not system_id:
        return _idk(question, "owner", ["doc and ticket titles", "system names"], now, "I could not tell which doc, ticket or system you mean.")
    team = svc.run("system_owner", system_id=system_id)
    ranked = brain.who_knows(svc, system_id)
    segs = []
    if team:
        segs.append(Segment(text=f"{system_id} is owned by the {team[0]['team']} team ({len(team[0]['members'])} people)."))
    src: list[dict[str, Any]] = []
    nodes, edges = [system_id], []
    if ranked:
        top = ranked[0]
        work = svc.run("person_work", person_id=top["person_id"], system_id=system_id)
        src = [{"id": w["id"], "kind": w["kind"], "text": w["text"], "url": w["url"]} for w in work]
        segs.append(Segment(text=f"Day to day, {top['name']} knows it best ({int(top['activity'])} authored or reviewed items).",
                            sources=[w["id"] for w in work]))
        nodes.append(top["person_id"]); edges.append([top["person_id"], "EXPERT_ON", system_id])
        if top["bus_factor_warning"]:
            segs.append(Segment(text=f"Bus-factor warning: nobody else has meaningful activity on {system_id}.", tone="warning"))
    return Answer(question=question, tool="owner", found=bool(segs), text=" ".join(s.text for s in segs), segments=segs,
                  path={"nodes": nodes, "edges": edges, "labels": {r["person_id"]: r["name"] for r in ranked[:1]}},
                  sources=src, searched=[f"system resolved: {system_id}"], as_of=now)


def _person_in(svc: GraphService, question: str, capitalised: bool = False) -> dict[str, Any] | None:
    """The one person named in the question. With `capitalised`, only a capitalised name counts ("Grace", not "grace period")."""
    words = re.findall(r"[A-Za-zÀ-ÿ]+", question)
    q = {w.lower() for w in words if not capitalised or w[0].isupper()}
    hits = [p for p in svc.run("people_full") if q & {w for w in re.findall(r"[a-zà-ÿ]+", p["name"].lower()) if len(w) > 2}]
    return hits[0] if len(hits) == 1 else None


def _answer_person(svc: GraphService, question: str, person: dict[str, Any], now: int) -> Answer:
    pid, name = person["id"], person["name"]
    systems = svc.run("person_systems", person_id=pid, now=now)
    owned = svc.run("person_owned", person_id=pid)
    decisions = svc.run("person_decisions", person_id=pid)
    tasks = [r for r in svc.run("inbox") if r["owner_id"] == pid and r["status"] == "open"]
    segs = [Segment(text=f"{name} is {person['role']} on the {person['team']} team.")]
    sources: list[dict[str, Any]] = []
    nodes, edges = [pid], []
    if systems:
        work = svc.run("person_work", person_id=pid, system_id=systems[0]["system_id"])
        sources += [{"id": w["id"], "kind": w["kind"], "text": w["text"], "url": w["url"]} for w in work]
        top = ", ".join(f"{s['system_id']} ({s['activity']} item{'s' * (s['activity'] != 1)})" for s in systems[:3])
        segs.append(Segment(text=f"Works mostly on {top}; last active {_d(systems[0]['last_ts'])}.", sources=[w["id"] for w in work]))
        for s in systems[:3]:
            nodes.append(s["system_id"]); edges.append([pid, "EXPERT_ON", s["system_id"]])
    if owned:
        docs = [o for o in owned if o["kind"] == "Doc"]
        tickets = [o for o in owned if o["kind"] == "Ticket"]
        sources += [{"id": o["id"], "kind": o["kind"], "text": o["title"], "url": o["url"]} for o in owned[:6]]
        segs.append(Segment(text=f"Owns {len(docs)} current docs and {len(tickets)} open tickets, including "
                                 f"{'; '.join(o['title'] for o in owned[:3])}.", sources=[o["id"] for o in owned[:6]]))
    if decisions:
        parts = [f"{d['summary']} ({d['system_id']}, {'in force' if not d['valid_to'] else 'superseded by ' + str(d['superseded_by'])})"
                 for d in decisions]
        segs.append(Segment(text=f"Decisions made: {'; '.join(parts)}."))
        for d in decisions:
            nodes.append(d["id"]); edges.append([d["id"], "DECIDED_BY", pid])
    if tasks:
        segs.append(Segment(text=f"{len(tasks)} drift fix{'es' * (len(tasks) != 1)} waiting on {name.split()[0]}: "
                                 f"{'; '.join(t['item_title'] for t in tasks)}.", sources=[t["item_id"] for t in tasks], tone="warning"))
    for r in brain.bus_factor(svc):
        if r["experts"][0]["id"] == pid:
            segs.append(Segment(text=f"Single point of knowledge: the only person with meaningful activity on {r['system_id']}.", tone="warning"))
    if pid in {b["person_id"] for b in brain.bridges(svc, top=1)}:
        segs.append(Segment(text=f"{name.split()[0]} is the strongest knowledge bridge between teams (betweenness)."))
    return Answer(question=question, tool="person", found=True, text=" ".join(s.text for s in segs), segments=segs,
                  path={"nodes": list(dict.fromkeys(nodes)), "edges": edges, "labels": {pid: name}}, sources=sources,
                  searched=[f"person resolved: {pid}"], as_of=now)


QSTOP = {"how", "do", "does", "did", "we", "i", "you", "our", "the", "a", "an", "to", "is", "are", "was", "of", "in", "on", "for",
         "and", "or", "what", "whats", "where", "when", "which", "who", "why", "can", "should", "it", "this", "that", "with", "be",
         "process", "procedure", "steps", "way"}


def _hybrid_hits(svc: GraphService, question: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Q1a vector + Q1b full-text, fused by reciprocal rank. A vector hit only counts within the distance threshold."""
    vec = svc.run("find_entry_points_vector", qvec=embed([question])[0])
    terms = [t for t in re.findall(r"[a-z0-9]+", question.lower()) if t not in QSTOP and len(t) > 1]
    # One full-text query per term (stemmed by the index), so a chunk's coverage is how many distinct terms it matches.
    cover: dict[str, int] = {}
    total: dict[str, float] = {}
    rows: dict[str, dict[str, Any]] = {}
    for t in dict.fromkeys(terms):
        for h in svc.run("find_entry_points_fulltext", terms=t):
            cover[h["chunk_id"]] = cover.get(h["chunk_id"], 0) + 1
            total[h["chunk_id"]] = total.get(h["chunk_id"], 0) + h["score"]
            rows.setdefault(h["chunk_id"], h)
    best_cover = max(cover.values(), default=0)
    txt = sorted((rows[c] for c in rows if cover[c] >= max(1, best_cover - 1)), key=lambda h: (cover[h["chunk_id"]], total[h["chunk_id"]]), reverse=True)
    fused: dict[str, float] = {}
    chunk: dict[str, dict[str, Any]] = {}
    for rank, h in enumerate([h for h in vec if h["score"] <= MAX_VECTOR_DISTANCE]):
        fused[h["chunk_id"]] = fused.get(h["chunk_id"], 0) + 1 / (60 + rank); chunk.setdefault(h["chunk_id"], h)
    for rank, h in enumerate(txt):
        fused[h["chunk_id"]] = fused.get(h["chunk_id"], 0) + 1 / (60 + rank); chunk.setdefault(h["chunk_id"], h)
    searched = [f"{h['src_id']} (vector distance {h['score']:.2f})" for h in vec[:3]]
    searched += [f"{h['src_id']} (keyword match: {' | '.join(terms)})" for h in txt[:3]]
    # Exact term coverage first (precise), the fused rank second; vector-only hits fill in when no keyword matches.
    order = sorted(fused, key=lambda c: (cover.get(c, 0), fused[c]), reverse=True)
    return [{**chunk[c], "cover": cover.get(c, 0)} for c in order], searched


def _answer_search(svc: GraphService, question: str, now: int, searched: list[str]) -> Answer:
    """Quote the closest passages verbatim (no generation) and flag any the graph knows are out of date."""
    hits, trace = _hybrid_hits(svc, question)
    searched = searched + trace
    if hits and hits[0]["cover"] >= 2:  # a passage matching several question terms: drop weaker, looser matches
        hits = [h for h in hits if h["cover"] >= hits[0]["cover"] - 1]
    best: dict[str, dict[str, Any]] = {}
    for h in hits:
        best.setdefault(h["src_id"], h)
    top = list(best.values())[:3]
    if not top:
        return _idk(question, "search", searched, now, "I searched documents and messages and found nothing relevant to that question.")
    info = {r["id"]: r for r in svc.run("sources_by_ids", ids=[h["src_id"] for h in top])}
    notes = _stale_notes(svc, [h["src_id"] for h in top])
    newer = [f["new_id"] for fs in notes.values() for f in fs if f["new_id"]]
    new_ev = {d["id"]: d["evidence"] for d in svc.run("decisions_by_ids", ids=newer)} if newer else {}
    sources: dict[str, dict[str, Any]] = {}
    segs: list[Segment] = []
    for h in top:  # most relevant first; a stale passage carries its warning right below it
        src = info[h["src_id"]]
        label = f"{src['kind']} \"{src['title']}\"" if src["kind"] != "Message" else f"Message {src['id']}"
        sources[src["id"]] = {"id": src["id"], "kind": src["kind"], "text": src["title"], "url": src["url"]}
        segs.append(Segment(text=f"{label}: “{h['text']}”", sources=[src["id"]]))
        for f in notes.get(src["id"], []):
            ev = [e for e in new_ev.get(f["new_id"], []) if e.get("id")]
            sources.update({e["id"]: _src(e) for e in ev})
            segs.append(Segment(text=_warning(f, src["kind"]), sources=[e["id"] for e in ev], tone="warning"))
    nodes = list(sources)
    edges = [[f["src_id"], "STALE_AFTER", f["new_id"]] for fs in notes.values() for f in fs if f["new_id"]]
    return Answer(question=question, tool="search", found=True, text=" ".join(s.text for s in segs), segments=segs,
                  path={"nodes": list(dict.fromkeys(nodes + [e[2] for e in edges])), "edges": edges},
                  sources=list(sources.values()), searched=searched, as_of=now)


def answer(svc: GraphService, question: str, as_of: int | None = None, intent: str | None = None, allow_llm: bool = True) -> Answer:
    """`intent` skips intent detection (and the LLM router): the MCP tools already know which tool they are.
    With `allow_llm=False`, unclear questions fall back to quoting documents instead of the LLM router."""
    now = int(time.time() * 1000)
    t = as_of or parse_as_of(question, now)
    intent = intent or _intent(question)
    searched: list[str] = []
    system_id = _system_by_name(svc, question)
    person = _person_in(svc, question, capitalised=intent is None) if intent in (None, "person") else None
    if intent == "person" and person is None:
        intent = None
    if person and intent in (None, "person"):
        return _answer_person(svc, question, person, now)
    if intent is None and allow_llm:  # unclear: let the LLM pick a tool from the vetted list
        route = llm.structured(
            f"Pick the tool for this question. Tools: why (a decision and its history), who_knows (expertise), "
            f"owner (who owns a doc, ticket or system), whats_changed (recent decisions), search (how-to or facts in docs), "
            f"whats_stale, bus_factor, bridges, unknown (not about the company).\n"
            f"Systems: {[s['id'] for s in svc.run('systems')]}\nQuestion: {question}",
            Route)
        intent, system_id = route.tool, system_id or route.system_id
        searched.append(f"LLM router chose: {route.tool}")
    if intent in (None, "unknown", "person"):  # nothing structured fits: quote the closest documents, or say so
        ans = _answer_search(svc, question, now, searched)
        if not ans.found and intent == "unknown":
            return _idk(question, "unknown", ans.searched, t, "That is not a question I can answer from the company graph.")
        return ans
    if intent == "search":
        return _answer_search(svc, question, now, searched)
    if intent == "whats_stale":
        return _answer_stale(svc, question, now)
    if intent == "whats_changed":
        return _answer_changes(svc, question, t)
    if intent == "owner":
        return _answer_owner(svc, question, now)
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
