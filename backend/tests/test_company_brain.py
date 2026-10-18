"""Company-brain coverage beyond "why": owners, people, recent changes, quoted search with stale warnings,
the self-audit, and the write-time contradiction check on a new doc (real LLM, cached)."""
import pytest

import brain
from agents import concierge, pipeline, steward
from agents.ingestor import IngestDoc


def ask(svc, q):
    return concierge.answer(svc, q, allow_llm=False)


def test_owner_of_a_doc_by_title_flags_it_stale(svc):
    a = ask(svc, "Who owns the onboarding doc?")
    assert a.tool == "owner" and "Sofia Alvarez owns it directly" in a.text
    warn = [s for s in a.segments if s.tone == "warning"]
    assert warn and "Redis" in warn[0].text and "D-02" in warn[0].text


def test_owner_of_unowned_doc_routes_to_team_expert(svc):
    a = ask(svc, "Who owns the schema registry ADR?")
    assert "ADR-011" in a.segments[0].sources and "Omar Haddad" in a.text and "nobody owns it directly" in a.text


def test_owner_of_a_system_is_its_team(svc):
    a = ask(svc, "Who owns billing-reconciler?")
    assert "Payments team" in a.text and "Priya Nair" in a.text and any(s.tone == "warning" for s in a.segments)


def test_person_profile(svc):
    a = ask(svc, "What does Aisha work on?")
    assert a.tool == "person" and "Platform Lead" in a.text and "auth-service" in a.text
    assert "Use Kafka as the event bus (event-bus, in force)" in a.text and "superseded by D-02" in a.text
    priya = ask(svc, "Tell me about Priya")
    assert any("Single point of knowledge" in s.text for s in priya.segments)


def test_whats_changed_window_and_empty_window(svc):
    a = ask(svc, "What changed since June?")
    assert a.tool == "whats_changed" and a.found
    assert [s for s in ("D-04", "D-06", "D-02") if any(s == n for n in a.path["nodes"])] == ["D-04", "D-06", "D-02"]
    assert "Migrate CI from Jenkins to GitHub Actions" in a.text and "MSG-006" in {x["id"] for x in a.sources}
    quiet = ask(svc, "What changed last week?")  # nothing on a fresh seed; says so and names the latest change
    assert not quiet.found and "most recent change" in quiet.text


def test_whats_stale_audits_existing_drift(svc):
    a = ask(svc, "Which docs are out of date?")
    assert a.found and a.segments[0].text.startswith("7 items")
    assert {"DOC-runbook-deploy", "DOC-api-v1-guide", "TKT-001"} <= {s["id"] for s in a.sources}


def test_search_quotes_docs_and_warns_when_stale(svc):
    a = ask(svc, "How do we deploy?")
    assert a.tool == "search" and a.found and "DOC-runbook-deploy" in {s["id"] for s in a.sources}
    warn = [s.text for s in a.segments if s.tone == "warning"]
    assert any("Jenkins" in w and "GitHub Actions" in w for w in warn)


def test_search_is_hybrid_and_ranks_by_term_coverage(svc):
    a = ask(svc, "How do I run auth flows locally?")
    assert a.sources[0]["id"] == "DOC-onboarding" and "local Redis" in a.segments[0].text
    assert any(s.tone == "warning" and "D-02" in s.text for s in a.segments)
    assert any("keyword match" in x for x in a.searched)
    assert not ask(svc, "What is the weather in Paris?").found


@pytest.mark.llm
def test_knowledge_health_and_dispatch(svc):
    h = brain.knowledge_health(svc)
    assert (h["stale_items"], h["untracked_stale"], h["health"]) == (7, 7, round(100 * (1 - 7 / h["items"]), 1))
    assert [u["id"] for u in h["unowned"]] == ["ADR-011"]
    created = steward.audit(svc)
    assert len(created) == 7 and all(t["status"] == "open" and t["draft"] for t in created)
    assert brain.knowledge_health(svc)["untracked_stale"] == 0
    assert steward.audit(svc) == []  # idempotent


DOC = IngestDoc(title="Local dev setup for auth-service", author="omar", text=(
    "Getting auth-service running on your laptop.\n\n"
    "Start a local Redis first: user sessions are stored in Redis, so login will fail without it.\n\n"
    "Access tokens expire after 15 minutes, so expect to log in again during long debugging sessions.\n\n"
    "Pushes run CI on GitHub Actions; check the Actions tab if your branch is red."))


@pytest.fixture(scope="module")
def doc_run(svc):
    from seed import load
    load(svc)
    return pipeline.ingest_doc(svc, DOC)


@pytest.mark.llm
def test_new_doc_contradiction_is_caught_at_write_time(svc, doc_run):
    bad = [c for c in doc_run["checks"] if not c["in_force"]]
    assert [(c["claim_id"], c["closed_by"]) for c in bad] == [("C-01", "D-02")]
    assert {c["claim_id"] for c in doc_run["checks"] if c["in_force"]} == {"C-04", "C-10"}
    assert "Redis" in bad[0]["quote"]
    (task,) = doc_run["tasks"]
    assert task["item_id"] == doc_run["doc_id"] and task["owner_id"] == "omar" and task["draft"]
    # only the new doc was dispatched, not the decision's other (historical) drift
    assert {r["item_id"] for r in svc.run("inbox")} == {doc_run["doc_id"]}


@pytest.mark.llm
def test_doc_check_handoff_chain_and_resume(svc, doc_run):
    row = next(r for r in svc.run("agent_timeline") if r["task_id"] == doc_run["task_id"])
    assert row["kind"] == "doc_check" and row["created_by"] == "Ingestor" and row["status"] == "done"
    assert [h["agent"] for h in row["handoffs"]] == ["Steward", "Concierge"]
    svc.raw("MATCH (t:Task {id:$id}) SET t.status='in_progress'", {"id": doc_run["task_id"]})
    assert doc_run["task_id"] in pipeline.resume(svc)
    assert len([r for r in svc.run("inbox") if r["item_id"] == doc_run["doc_id"]]) == 1  # resume did not duplicate


@pytest.mark.llm
def test_new_doc_is_searchable_and_flagged(svc, doc_run):
    a = ask(svc, "Who owns the local dev setup doc?")
    assert "Omar Haddad owns it directly" in a.text and any("D-02" in s.text for s in a.segments if s.tone == "warning")


@pytest.mark.llm
def test_second_fix_on_same_doc_builds_on_the_first(svc):
    """Audit fix approved first (sessions), then the live Kafka reversal hits the same onboarding guide."""
    import json
    import time
    from pathlib import Path

    from agents.ingestor import IngestMessage
    from seed import load
    load(svc)
    first = next(t for t in steward.audit(svc) if t["item_id"] == "DOC-onboarding")
    v2 = brain.approve(svc, first["task_id"])["new_version_id"]
    claims = lambda i: {r[0] for r in svc.raw("MATCH ({id:$i})-[:ASSERTS]->(c:Claim) RETURN c.id", {"i": i}).result_set}
    assert claims(v2) == {"C-02", "C-04", "C-07"}  # new sessions claim, other facts carried over, stale one dropped

    live = json.loads((Path(__file__).parent.parent.parent / "data" / "northwind" / "live_reversal.json").read_text())
    run = pipeline.ingest(svc, IngestMessage(channel=live["channel"], author=live["author"], text=live["text"],
                                             ts=int(time.time() * 1000) - 60_000))
    assert (run["docs"], run["tickets"]) == (3, 2)  # the fixed onboarding guide is still caught, as its new version
    second = next(t for t in run["tasks"] if t["item_id"] == v2)
    v3 = brain.approve(svc, second["task_id"])["new_version_id"]
    assert "C-07" not in claims(v3) and {"C-02", "C-04"} <= claims(v3) and len(claims(v3)) == 3
    assert v3 not in {r["item_id"] for r in brain.drift_audit(svc)}  # fully current again
