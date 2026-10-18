"""Brain operations: thin composition over the named Cypher templates.

No Cypher lives here. Each function calls templates and combines results (normalisation, ranking).
"""
import time
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


def owner_of(svc: GraphService, item_id: str) -> dict[str, Any]:
    """Accountable owner of a doc/ticket: the direct owner, else the owning team's top expert on the item's system."""
    route = svc.run("route_to_owner", item_id=item_id)[0]
    if route["owner_id"]:
        return {"owner_id": route["owner_id"], "routed_via": "direct owner", "team": route["team"], "system_id": route["system_id"]}
    scores = {r["person_id"]: r["score"] for r in who_knows(svc, route["system_id"])}
    members = route["team_member_ids"]
    return {"owner_id": max(members, key=lambda m: scores.get(m, 0)) if members else None,
            "routed_via": f"{route['team']} team, top expertise on {route['system_id']}",
            "team": route["team"], "system_id": route["system_id"]}


def whats_stale(svc: GraphService, new_decision_id: str) -> list[dict[str, Any]]:
    """Every doc / open ticket made wrong by `new_decision_id`, each with a resolved accountable owner."""
    items = svc.run("whats_stale", new_id=new_decision_id)
    for it in items:
        o = owner_of(svc, it["item_id"])
        it["owner_id"], it["routed_via"] = o["owner_id"], o["routed_via"]
    return items


def drift_audit(svc: GraphService) -> list[dict[str, Any]]:
    """Everything in the graph that already contradicts a newer decision, tracked by a drift task or not."""
    names = {p["id"]: p["name"] for p in svc.run("people")}
    rows = svc.run("drift_audit")
    for r in rows:
        o = owner_of(svc, r["item_id"])
        r["owner_id"], r["owner_name"], r["routed_via"] = o["owner_id"], names.get(o["owner_id"]), o["routed_via"]
    return rows


def knowledge_health(svc: GraphService) -> dict[str, Any]:
    """One read of how trustworthy the brain is right now: drift, ownership gaps, single points of knowledge."""
    st = {k: (int(v) if isinstance(v, float) else v) for k, v in svc.run("knowledge_stats")[0].items()}
    drift = drift_audit(svc)
    stale_items = {r["item_id"] for r in drift}
    untracked = {r["item_id"] for r in drift if not r["task_id"] or r["task_status"] == "rejected"}
    unowned = [u for u in st.pop("unowned") if u]
    return {
        **st,
        "stale_items": len(stale_items),
        "untracked_stale": len(untracked),
        "health": round(100 * (1 - len(stale_items) / st["items"]), 1) if st["items"] else 100.0,
        "drift": drift,
        "unowned": unowned,
        "bus_factor": bus_factor(svc),
        "bridges": bridges(svc),
    }


def approve(svc: GraphService, task_id: str) -> dict[str, Any]:
    """Human approval: create the new version node (old one kept) and close the task."""
    row = next((r for r in svc.run("inbox") if r["task_id"] == task_id), None)
    if not row or row["status"] != "open":
        raise ValueError(f"task {task_id} is not open")
    new_id = f"{row['item_id']}@{row['decision_id']}"
    template = "approve_doc" if row["item_label"] == "Doc" else "approve_ticket"
    made = svc.run(template, task_id=task_id, new_id=new_id, now=int(time.time() * 1000))
    if not made:
        raise ValueError(f"task {task_id} could not be applied")
    old_id = made[0]["old_id"]  # the latest version, which may already carry an earlier approved fix
    svc.run("copy_knowledge", old_id=old_id, new_id=new_id)
    svc.run("copy_about", old_id=old_id, new_id=new_id)
    svc.run("copy_owner", old_id=old_id, new_id=new_id)
    return {"task_id": task_id, "new_version_id": new_id, "status": "approved"}


def reject(svc: GraphService, task_id: str) -> dict[str, Any]:
    if not svc.run("reject_task", task_id=task_id, now=int(time.time() * 1000)):
        raise ValueError(f"task {task_id} is not open")
    return {"task_id": task_id, "status": "rejected"}
