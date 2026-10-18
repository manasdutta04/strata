"""Coordination: the three agents share state only through the graph (Task nodes + HANDED_TO edges).

Ingestor creates the run Task -> hands to Steward (drafts fixes) -> hands to Concierge (summarises, closes).
Every step persists before the next begins, so `resume` can finish interrupted runs after a restart.
A new doc follows the same chain with a `doc_check` Task: the Steward opens a fix for each claim it states
that a newer decision has closed.
"""
import time
from typing import Any

from agents import ingestor, steward
from graph.service import GraphService


def _handoff(svc: GraphService, task_id: str, agent: str, status: str = "in_progress") -> None:
    svc.run("handoff_task", task_id=task_id, agent=agent, status=status, now=int(time.time() * 1000))


def _finish(svc: GraphService, run_task: str, decision_id: str) -> dict[str, Any]:
    tasks = steward.run(svc, decision_id)  # idempotent: safe to repeat after a crash
    summary = {"decision_id": decision_id, "stale_items": len(tasks),
               "docs": sum(t["item_label"] == "Doc" for t in tasks), "tickets": sum(t["item_label"] == "Ticket" for t in tasks)}
    _handoff(svc, run_task, "Concierge", status="done")
    return {**summary, "tasks": tasks}


def ingest(svc: GraphService, msg: ingestor.IngestMessage) -> dict[str, Any]:
    res = ingestor.run(svc, msg)
    if res["status"] != "ingested":
        return res
    _handoff(svc, res["task_id"], "Steward")
    return {**res, **_finish(svc, res["task_id"], res["decision_id"])}


def _finish_doc(svc: GraphService, run_task: str, doc_id: str) -> dict[str, Any]:
    checks = svc.run("doc_check", doc_id=doc_id)
    conflicts = [c for c in checks if not c["in_force"]]
    tasks = [t for did in dict.fromkeys(c["closed_by"] for c in conflicts if c["closed_by"]) for t in steward.run(svc, did, {doc_id})]
    _handoff(svc, run_task, "Concierge", status="done")
    return {"checks": checks, "conflicts": len(conflicts), "tasks": tasks}


def ingest_doc(svc: GraphService, doc: ingestor.IngestDoc) -> dict[str, Any]:
    res = ingestor.run_doc(svc, doc)
    _handoff(svc, res["task_id"], "Steward")
    return {**res, **_finish_doc(svc, res["task_id"], res["doc_id"])}


def resume(svc: GraphService) -> list[str]:
    """Finish pipeline runs that were interrupted (status in_progress). Returns the task ids resumed."""
    resumed = []
    for t in svc.run("resume_tasks"):
        if t["kind"] == "review" and t["status"] == "in_progress" and t["decision_id"]:
            if "Steward" not in t["agents"]:
                _handoff(svc, t["task_id"], "Steward")
            _finish(svc, t["task_id"], t["decision_id"])
            resumed.append(t["task_id"])
        elif t["kind"] == "doc_check" and t["status"] == "in_progress" and t["doc_id"]:
            if "Steward" not in t["agents"]:
                _handoff(svc, t["task_id"], "Steward")
            _finish_doc(svc, t["task_id"], t["doc_id"])
            resumed.append(t["task_id"])
    return resumed
