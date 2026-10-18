"""Steward agent: finds knowledge made wrong by a new decision, resolves owners, drafts fixes.

Staleness and ownership come from the graph (whats_stale, route_to_owner, who_knows). The LLM only
drafts the diff text. Nothing is applied here: each fix becomes an open Task awaiting human approval.
"""
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import brain
import llm
from graph.service import GraphService

DRAFT_PROMPT = """You maintain company documentation. A decision changed and this {kind} is now wrong.

New decision: {summary}
Why: {rationale}
Stale statement in the {kind}: "{stale_text}"

{kind} title: {title}
{kind} text:
{text}

Write a minimal fix as a diff: only lines that change, each prefixed with "- " (remove) or "+ " (add),
preceded by one line starting with "@@ " naming the section. Do not add commentary.
"""


def _draft(svc: GraphService, item: dict[str, Any], decision: dict[str, Any]) -> str:
    body = svc.run("item_text", item_id=item["item_id"])[0]
    text = "\n".join(sorted(body["chunks"])) or body["title"]
    if body["changes"]:
        text += "\n\nFixes already applied to this " + item["item_label"].lower() + ":\n" + "\n".join(body["changes"])
    prompt = DRAFT_PROMPT.format(
        kind=item["item_label"].lower(), summary=decision["summary"], rationale=decision["rationale"] or "",
        stale_text=item["stale_text"], title=body["title"], text=text,
    )
    return llm.complete(prompt).strip()


def run(svc: GraphService, decision_id: str, item_ids: set[str] | None = None) -> list[dict[str, Any]]:
    """Create one open drift Task per stale item (only `item_ids` if given). Idempotent: items that already have a task are skipped."""
    decision = svc.run("decisions_by_ids", ids=[decision_id])[0]
    stale = [s for s in brain.whats_stale(svc, decision_id) if item_ids is None or s["item_id"] in item_ids]
    have = {r["item_id"] for r in svc.run("inbox") if r["decision_id"] == decision_id}
    todo = [s for s in stale if s["item_id"] not in have]
    with ThreadPoolExecutor(max_workers=5) as pool:
        drafts = list(pool.map(lambda it: _draft(svc, it, decision), todo))
    now = int(time.time() * 1000)
    for item, draft in zip(todo, drafts):
        svc.run("create_drift_task", item_id=item["item_id"], decision_id=decision_id, owner_id=item["owner_id"],
                task_id=f"TASK-{decision_id}-{item['item_id']}", draft=draft, now=now)
    return [r for r in svc.run("inbox") if r["decision_id"] == decision_id and (item_ids is None or r["item_id"] in item_ids)]


def audit(svc: GraphService) -> list[dict[str, Any]]:
    """Self-audit: open drift tasks for every item that already contradicts a newer decision but is not tracked yet."""
    untracked: dict[str, set[str]] = {}
    for r in svc.run("drift_audit"):
        if not r["task_id"]:
            untracked.setdefault(r["decision_id"], set()).add(r["item_id"])
    return [t for did, items in untracked.items() for t in run(svc, did, items)]
