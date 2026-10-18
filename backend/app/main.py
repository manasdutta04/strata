"""FastAPI routes. Thin: every route calls brain / agents / memory, which call named Cypher templates."""
import threading
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import brain
from agents import concierge, pipeline, steward
from agents.ingestor import IngestDoc, IngestMessage
from config import settings
from graph.service import GraphService
from memory import personal

svc = GraphService()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Work interrupted by a crash resumes from Task status in the graph.
    threading.Thread(target=pipeline.resume, args=(svc,), daemon=True).start()
    yield


app = FastAPI(title="Strata", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()], allow_methods=["*"], allow_headers=["*"])


class AskRequest(BaseModel):
    question: str
    user_id: str = "demo"
    session_id: str | None = None
    as_of: int | None = None
    record: bool = True  # False for UI re-runs (time slider) so they do not rewrite what the user last saw


class SessionRequest(BaseModel):
    user_id: str = "demo"
    session_id: str | None = None


@app.get("/health")
def health() -> dict[str, Any]:
    svc.raw("RETURN 1")
    return {"ok": True}


@app.post("/ask")
def ask(req: AskRequest) -> concierge.Answer:
    ans = concierge.answer(svc, req.question, req.as_of)
    if req.record:
        personal.record(req.user_id, req.session_id or "default", req.question, ans.shown_decision)
    return ans


@app.post("/session/start")
def session_start(req: SessionRequest) -> dict[str, Any]:
    sid = req.session_id or f"S-{uuid.uuid4().hex[:8]}"
    return {"session_id": sid, "changes": personal.session_start(svc, req.user_id, sid)}


@app.post("/ingest")
def ingest(msg: IngestMessage) -> dict[str, Any]:
    try:
        return pipeline.ingest(svc, msg)
    except ValueError as e:  # unknown author or unusable LLM output
        raise HTTPException(422, str(e)) from e


@app.post("/ingest/doc")
def ingest_doc(doc: IngestDoc) -> dict[str, Any]:
    try:
        return pipeline.ingest_doc(svc, doc)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@app.get("/knowledge-health")
def knowledge_health() -> dict[str, Any]:
    return brain.knowledge_health(svc)


@app.post("/audit/dispatch")
def audit_dispatch() -> dict[str, Any]:
    """Hand every untracked contradiction to the Steward, which drafts a fix for each (still human-approved)."""
    tasks = steward.audit(svc)
    return {"created": len(tasks), "tasks": tasks}


@app.get("/inbox")
def inbox() -> list[dict[str, Any]]:
    rows = svc.run("inbox")
    for r in rows:
        reason = svc.run("stale_reason", task_id=r["task_id"])
        r["why_stale"] = reason[0] if reason else None
    return rows


@app.post("/tasks/{task_id}/approve")
def approve(task_id: str) -> dict[str, Any]:
    try:
        return brain.approve(svc, task_id)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


@app.post("/tasks/{task_id}/reject")
def reject(task_id: str) -> dict[str, Any]:
    try:
        return brain.reject(svc, task_id)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


@app.get("/agents/timeline")
def timeline() -> list[dict[str, Any]]:
    return svc.run("agent_timeline")


@app.get("/who-knows/{system_id}")
def who_knows(system_id: str) -> list[dict[str, Any]]:
    return brain.who_knows(svc, system_id)


@app.get("/bus-factor")
def bus_factor() -> list[dict[str, Any]]:
    return brain.bus_factor(svc)


@app.get("/bridges")
def bridges() -> list[dict[str, Any]]:
    return brain.bridges(svc)


@app.get("/informal-teams")
def informal_teams() -> list[dict[str, Any]]:
    names = {p["id"]: p["name"] for p in svc.run("people")}
    return [{"community": r["community"], "members": [names[m] for m in r["member_ids"]]} for r in svc.run("informal_teams")]


@app.get("/graph")
def graph_view() -> list[dict[str, Any]]:
    return svc.run("graph_view")


@app.get("/systems")
def systems() -> list[str]:
    return [s["id"] for s in svc.run("systems")]


@app.post("/demo/reset")
def reset() -> dict[str, Any]:
    from seed import load
    svc.reset_user_graphs()
    return load(svc)
