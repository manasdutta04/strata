"""Ingestor agent: turns one chat message into a Decision in the graph.

The LLM extracts structure, grounded in the decisions currently in force (so "what does this
supersede?" is a choice among real graph nodes, never an invented id). It then writes through
named templates and closes the old decision with the real `supersede` template.
"""
import time
from typing import Any

from pydantic import BaseModel

import llm
from embeddings import embed
from graph.service import GraphService

PROMPT = """You extract company decisions from chat messages.

Message (channel #{channel}, author {author}):
\"\"\"{text}\"\"\"

Systems: {systems}

Decisions currently in force (id | system | summary):
{current}

Decide whether the message announces or reverses a decision about one of the systems.
- is_decision: true only if a decision is announced or changed.
- system_id: the single system it affects, from the list above (null if none).
- summary: one short sentence stating the new decision.
- rationale: the reason given, one sentence.
- new_claim: a present-tense factual statement that becomes true (e.g. "The event bus runs on X.").
- supersedes_id: the id of the decision in force that this message replaces, only from the list above, else null.
- confidence: 0 to 1.
"""


class Extraction(BaseModel):
    is_decision: bool
    system_id: str | None = None
    summary: str = ""
    rationale: str = ""
    new_claim: str = ""
    supersedes_id: str | None = None
    confidence: float = 0.0


class IngestMessage(BaseModel):
    channel: str
    author: str  # person id or name
    text: str
    ts: int | None = None


def _resolve_author(svc: GraphService, author: str) -> dict[str, str]:
    people = svc.run("people")
    for p in people:
        if author.lower() in (p["id"].lower(), p["name"].lower(), p["name"].split()[0].lower()):
            return p
    raise ValueError(f"unknown author: {author}")


def extract(svc: GraphService, msg: IngestMessage, author_name: str) -> Extraction:
    current = svc.run("current_decisions")
    prompt = PROMPT.format(
        channel=msg.channel, author=author_name, text=msg.text,
        systems=", ".join(s["id"] for s in svc.run("systems")),
        current="\n".join(f"{c['id']} | {c['system_id']} | {c['summary']}" for c in current),
    )
    ex = llm.structured(prompt, Extraction)
    valid = {c["id"] for c in current}
    if ex.supersedes_id not in valid:
        ex.supersedes_id = None
    return ex


def run(svc: GraphService, msg: IngestMessage) -> dict[str, Any]:
    """Returns {status, decision_id, supersedes_id, task_id, extraction}; status 'ignored' if no decision."""
    author = _resolve_author(svc, msg.author)
    ex = extract(svc, msg, author["name"])
    systems = {s["id"] for s in svc.run("systems")}
    if not ex.is_decision or ex.system_id not in systems:
        return {"status": "ignored", "reason": "no decision about a known system", "extraction": ex.model_dump()}

    now = int(time.time() * 1000)
    ts = msg.ts or now
    counts = svc.run("count_nodes")[0]
    decision_id, claim_id = f"D-{counts['decisions'] + 1:02d}", f"C-{counts['claims'] + 1:02d}"
    msg_id = f"MSG-LIVE-{ts}"
    svc.run("ingest_decision", system_id=ex.system_id, author_id=author["id"], msg_id=msg_id, channel=msg.channel,
            text=msg.text, ts=ts, decision_id=decision_id, summary=ex.summary, rationale=ex.rationale,
            confidence=ex.confidence, claim_id=claim_id, claim_text=ex.new_claim, now=now)
    svc.run("add_message_chunk", msg_id=msg_id, decision_id=decision_id, chunk_id=f"{msg_id}#0", vec=embed([msg.text])[0])
    if ex.supersedes_id:
        svc.run("supersede", new_id=decision_id, old_id=ex.supersedes_id)

    task_id = f"RUN-{decision_id}"
    svc.run("create_pipeline_task", task_id=task_id, decision_id=decision_id, summary=ex.summary, now=now)
    return {"status": "ingested", "decision_id": decision_id, "supersedes_id": ex.supersedes_id,
            "task_id": task_id, "extraction": ex.model_dump()}
