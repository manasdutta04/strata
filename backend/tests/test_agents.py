"""End-to-end: Concierge answers, the live drift pipeline (real LLM, cached), approval, memory, resume."""
import json
import time
from pathlib import Path

import pytest

import brain
from agents import concierge, pipeline
from agents.ingestor import IngestMessage
from memory import personal

LIVE = json.loads((Path(__file__).parent.parent.parent / "data" / "northwind" / "live_reversal.json").read_text())
LIVE["ts"] = int(time.time() * 1000) - 60_000  # the decision happened a minute ago (real clock)


def test_concierge_golden_answers(svc):
    a = concierge.answer(svc, "Why do we use Postgres for sessions?")
    assert a.found and "Postgres" in a.text and "Redis" in a.text and any(s["id"] == "MSG-004" for s in a.sources)
    assert ["D-02", "D-01"] in [[e[2] and e[0], e[2]] for e in a.path["edges"] if e[1] == "SUPERSEDES"]
    old = concierge.answer(svc, "Why did we use Redis for sessions? (as of April)")
    assert "later superseded" in old.text
    who = concierge.answer(svc, "Who knows the billing reconciler?")
    assert "Priya" in who.segments[0].text and "Bus-factor warning" in who.text
    assert "Reyes" in concierge.answer(svc, "Who connects Payments and Data?").text


def test_concierge_says_idk_without_evidence(svc):
    a = concierge.answer(svc, "Why do we use MongoDB for analytics?")
    assert not a.found and a.text.startswith("I don't know") and a.searched


@pytest.fixture(scope="module")
def live_run(svc):
    from seed import load
    load(svc)
    personal.record("alice", "S1", "Why is the event bus on Kafka?", concierge.answer(svc, "Why is the event bus on Kafka?").shown_decision)
    return pipeline.ingest(svc, IngestMessage(channel=LIVE["channel"], author=LIVE["author"], text=LIVE["text"], ts=LIVE["ts"]))


def test_live_reversal_pipeline(svc, live_run):
    assert live_run["supersedes_id"] == "D-07"
    assert (live_run["docs"], live_run["tickets"]) == (3, 2)
    assert all(t["owner_id"] and t["draft"] for t in live_run["tasks"])
    assert svc.raw("MATCH (d:Decision {id:'D-07'}) RETURN d.valid_to").result_set[0][0] == LIVE["ts"]


def test_handoff_chain_is_in_the_graph(svc, live_run):
    row = next(r for r in svc.run("agent_timeline") if r["task_id"] == live_run["task_id"])
    assert row["created_by"] == "Ingestor" and row["status"] == "done"
    assert [h["agent"] for h in row["handoffs"]] == ["Steward", "Concierge"]


def test_personal_memory_reports_change(svc, live_run):
    changes = personal.session_start(svc, "alice", "S2")
    assert [c["system_id"] for c in changes] == ["event-bus"] and changes[0]["now_in_force"] == live_run["decision_id"]
    assert personal.session_start(svc, "alice", "S3") == []  # reported once


def test_time_travel_flips_the_answer(svc, live_run):
    before = concierge.answer(svc, "Why is the event bus on Kafka?", as_of=LIVE["ts"] - 86400000)
    after = concierge.answer(svc, "Why is the event bus on Kafka?", as_of=LIVE["ts"] + 1000)
    assert "Kafka" in before.segments[0].text and "Redis Streams" in after.segments[0].text


def test_approve_creates_version_and_reject_keeps_item_stale(svc, live_run):
    ids = {t["item_id"]: t["task_id"] for t in live_run["tasks"]}
    res = brain.approve(svc, ids["DOC-event-bus-readme"])
    assert res["new_version_id"] == "DOC-event-bus-readme@" + live_run["decision_id"]
    brain.reject(svc, ids["ADR-011"])
    still = {i["item_id"] for i in brain.whats_stale(svc, live_run["decision_id"])}
    assert "DOC-event-bus-readme" not in still and "ADR-011" in still  # fixed vs. rejected
    with pytest.raises(ValueError):
        brain.approve(svc, ids["DOC-event-bus-readme"])  # cannot approve twice


def test_resume_finishes_interrupted_runs(svc, live_run):
    svc.raw("MATCH (t:Task {id:$id}) SET t.status='in_progress'", {"id": live_run["task_id"]})
    assert pipeline.resume(svc) == [live_run["task_id"]]
    assert svc.raw("MATCH (t:Task {id:$id}) RETURN t.status", {"id": live_run["task_id"]}).result_set[0][0] == "done"


def test_historical_answers_are_not_remembered_as_seen(svc):
    now = concierge.answer(svc, "Why do we use Postgres for sessions?")
    april = concierge.answer(svc, "Why did we use Redis for sessions? (as of April)")
    assert now.shown_decision and now.shown_decision["decision_id"] == "D-02"
    assert april.shown_decision is None
