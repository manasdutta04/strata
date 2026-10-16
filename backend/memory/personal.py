"""Personal memory: one FalkorDB graph per user (`strata_user_<id>`).

(:Session)-[:ASKED]->(:Question)-[:SHOWN]->(:DecisionRef). On a new session we compare each
remembered DecisionRef with the decision now in force in the company graph and report changes.
"""
import re
import time
import uuid
from typing import Any

import brain
from graph.service import GraphService


def _user_graph(user_id: str) -> GraphService:
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", user_id)
    return GraphService(f"strata_user_{safe}")


def record(user_id: str, session_id: str, question: str, shown: dict[str, Any] | None) -> None:
    """Remember a question and, if the answer showed a decision, which version of it."""
    g = _user_graph(user_id)
    qid, now = f"Q-{uuid.uuid4().hex[:10]}", int(time.time() * 1000)
    g.run("p_record_question", sid=session_id, qid=qid, text=question, now=now)
    if shown:
        g.run("p_record_shown", qid=qid, decision_id=shown["decision_id"], system_id=shown["system_id"],
              valid_from=shown["valid_from"])


def session_start(company: GraphService, user_id: str, session_id: str) -> list[dict[str, Any]]:
    """Decisions this user was shown that have since been replaced. Reported once, then re-recorded."""
    g = _user_graph(user_id)
    changes = []
    now = int(time.time() * 1000)
    for row in g.run("p_last_shown"):
        current = brain.why(company, row["system_id"], now)
        if current and current["decision_id"] != row["decision_id"]:
            changes.append({
                "system_id": row["system_id"],
                "question": row["question"],
                "last_asked": row["last_ts"],
                "was_shown": row["decision_id"],
                "now_in_force": current["decision_id"],
                "summary": current["summary"],
                "changed_at": current["valid_from"],
            })
            record(user_id, session_id, "[session notice]",
                   {"decision_id": current["decision_id"], "system_id": row["system_id"], "valid_from": current["valid_from"]})
    return changes
