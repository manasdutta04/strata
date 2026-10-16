"""Brain operations: thin composition over the named Cypher templates.

No Cypher lives here. Each function calls templates and combines results (normalisation, ranking).
"""
from typing import Any

from graph.service import GraphService

BUS_THRESHOLD = 3


def why(svc: GraphService, system_id: str, t: int) -> dict[str, Any] | None:
    """Decision in force for `system_id` at time `t`, with lineage, evidence and who decided."""
    rows = svc.run("why", system_id=system_id, t=t)
    if not rows:
        return None
    r = rows[0]
    r["superseded_by"] = [s for s in r["superseded_by"] if s.get("id")]
    r["evidence"] = [e for e in r["evidence"] if e.get("id")]
    r["lineage"] = [chain for chain in r["lineage"] if chain]
    return r


def who_knows(svc: GraphService, system_id: str) -> list[dict[str, Any]]:
    """Rank people for a system: normalised activity x (1 + PageRank), with a bridge badge from betweenness."""
    activity = svc.run("who_knows_activity", system_id=system_id)
    if not activity:
        return []
    pr = {r["person_id"]: r["score"] for r in svc.run("pagerank")}
    bt = {r["person_id"]: r["score"] for r in svc.run("betweenness")}
    top_bt = max(bt.values(), default=0) or 1
    peak = max(a["activity"] for a in activity)
    bus = {r["system_id"] for r in svc.run("bus_factor", threshold=BUS_THRESHOLD)}
    out = []
    for a in activity:
        norm = a["activity"] / peak
        score = norm * (1 + pr.get(a["person_id"], 0))
        out.append({
            **a,
            "normalised_activity": round(norm, 3),
            "pagerank": pr.get(a["person_id"], 0),
            "betweenness": bt.get(a["person_id"], 0),
            "knowledge_bridge": bt.get(a["person_id"], 0) >= 0.5 * top_bt,
            "score": round(score, 4),
            "bus_factor_warning": system_id in bus,
        })
    return sorted(out, key=lambda r: r["score"], reverse=True)


def bus_factor(svc: GraphService) -> list[dict[str, Any]]:
    return svc.run("bus_factor", threshold=BUS_THRESHOLD)


def bridges(svc: GraphService, top: int = 3) -> list[dict[str, Any]]:
    """People with highest betweenness over the collaboration graph."""
    people = {r["id"]: r["name"] for r in svc.run("people")}
    return [{**r, "name": people[r["person_id"]]} for r in svc.run("betweenness")[:top]]


def whats_stale(svc: GraphService, new_decision_id: str) -> list[dict[str, Any]]:
    """Every doc / open ticket made wrong by `new_decision_id`, each with a resolved accountable owner."""
    items = svc.run("whats_stale", new_id=new_decision_id)
    for it in items:
        route = svc.run("route_to_owner", item_id=it["item_id"])[0]
        if route["owner_id"]:
            it["owner_id"], it["routed_via"] = route["owner_id"], "direct owner"
        else:
            scores = {r["person_id"]: r["score"] for r in who_knows(svc, route["system_id"])}
            members = route["team_member_ids"]
            it["owner_id"] = max(members, key=lambda m: scores.get(m, 0))
            it["routed_via"] = f"{route['team']} team, top expertise on {route['system_id']}"
    return items
