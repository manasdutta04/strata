"""Ingestor agent: turns one chat message into a Decision, or one new doc into claims, in the graph.

The LLM extracts structure, grounded in the decisions currently in force (so "what does this
supersede?" is a choice among real graph nodes, never an invented id). It then writes through
named templates and closes the old decision with the real `supersede` template.

For a doc, the LLM only maps sentences to known Claim ids (in force or closed). Whether the doc is
wrong is then a graph question (`doc_check`): does it assert a claim some newer decision closed?
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


DOC_PROMPT = """You check a new company document against facts the company already knows.

Document "{title}" (written by {author}):
\"\"\"{text}\"\"\"

Systems: {systems}

Known facts (id | system | status | fact):
{claims}

- system_id: the single system the document is mainly about, from the list above (null if none).
- asserts: each known fact the document states or relies on, as {{"claim_id", "quote"}}. claim_id only from the list
  above, including facts that are no longer in force if the document states them. quote: the exact sentence from the
  document. Leave out facts the document does not state.
"""


class Assertion(BaseModel):
    claim_id: str
    quote: str = ""


class DocExtraction(BaseModel):
    system_id: str | None = None
    asserts: list[Assertion] = []


class IngestDoc(BaseModel):
    title: str
    text: str
    author: str  # person id or name
    kind: str = "readme"


def extract_doc(svc: GraphService, doc: IngestDoc, author_name: str) -> DocExtraction:
    claims = svc.run("all_claims")
    prompt = DOC_PROMPT.format(
        title=doc.title, author=author_name, text=doc.text,
        systems=", ".join(s["id"] for s in svc.run("systems")),
        claims="\n".join(f"{c['id']} | {c['system_id']} | {'in force' if c['valid_to'] is None else 'no longer true'} | {c['text']}"
                         for c in claims),
    )
    ex = llm.structured(prompt, DocExtraction)
    valid = {c["id"] for c in claims}
    ex.asserts = [a for a in ex.asserts if a.claim_id in valid]  # only real claim nodes, never invented ids
    if ex.system_id not in {s["id"] for s in svc.run("systems")}:
        ex.system_id = None
    return ex


def run_doc(svc: GraphService, doc: IngestDoc) -> dict[str, Any]:
    """Write the doc, its chunks and ASSERTS edges, then open the coordination Task. Returns {doc_id, task_id, extraction}."""
    author = _resolve_author(svc, doc.author)
    ex = extract_doc(svc, doc, author["name"])
    now = int(time.time() * 1000)
    doc_id = f"DOC-LIVE-{now}"
    svc.run("ingest_doc", doc_id=doc_id, author_id=author["id"], title=doc.title, kind=doc.kind, now=now)
    if ex.system_id:
        svc.run("doc_about", doc_id=doc_id, system_id=ex.system_id)
    paras = [p.strip() for p in doc.text.split("\n\n") if p.strip()] or [doc.text.strip()]
    for i, (para, vec) in enumerate(zip(paras, embed(paras))):
        svc.run("add_doc_chunk", doc_id=doc_id, chunk_id=f"{doc_id}#{i}", text=para, vec=vec)
    for a in ex.asserts:
        svc.run("doc_asserts", doc_id=doc_id, claim_id=a.claim_id, quote=a.quote)
    task_id = f"CHECK-{doc_id}"
    svc.run("create_doc_task", task_id=task_id, doc_id=doc_id, title=doc.title, now=now)
    return {"status": "ingested", "doc_id": doc_id, "task_id": task_id, "extraction": ex.model_dump()}
