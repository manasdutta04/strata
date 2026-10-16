"""Golden-question tests: these must be green before recording the demo."""
from datetime import datetime, timezone

import brain


def ms(date: str) -> int:
    return int(datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)


def test_why_postgres_for_sessions(svc):
    r = brain.why(svc, "session-store", ms("2026-10-16"))
    assert r["decision_id"] == "D-02" and r["decided_by"] == "leo"
    assert ["D-02", "D-01"] in r["lineage"]
    assert any(e["kind"] == "Message" and "Postgres" in e["text"] for e in r["evidence"])


def test_why_redis_as_of_april_marked_superseded(svc):
    r = brain.why(svc, "session-store", ms("2026-04-15"))
    assert r["decision_id"] == "D-01"
    assert [s["id"] for s in r["superseded_by"]] == ["D-02"]


def test_who_knows_billing_reconciler(svc):
    ranked = brain.who_knows(svc, "billing-reconciler")
    assert ranked[0]["person_id"] == "priya" and ranked[0]["bus_factor_warning"]
    assert [b["system_id"] for b in brain.bus_factor(svc)] == ["billing-reconciler"]


def test_knowledge_bridge_is_tomas(svc):
    assert brain.bridges(svc, top=1)[0]["person_id"] == "tomas"


def test_informal_cross_team_cluster(svc):
    groups = [set(r["member_ids"]) for r in svc.run("informal_teams")]
    assert {"ben", "yuki", "theo"} in groups


def test_historical_session_reversal_is_stale_in_exactly_three_places(svc):
    ids = {i["item_id"] for i in brain.whats_stale(svc, "D-02")}
    assert ids == {"DOC-onboarding", "DOC-auth-readme", "TKT-001"}


def _apply_live_reversal(svc):
    """Stand-in for the Ingestor: insert the new Decision, then call the real supersede template."""
    svc.raw("MATCH (n {id:'D-LIVE'}) DETACH DELETE n")
    svc.raw("MATCH (n {id:'C-LIVE'}) DETACH DELETE n")
    svc.raw("MATCH (d:Decision {id:'D-07'}) SET d.valid_to = NULL")
    svc.raw("MATCH (c:Claim {id:'C-07'}) SET c.valid_to = NULL")
    svc.raw("MATCH (:Decision {id:'D-07'})<-[r:SUPERSEDES]-() DELETE r")
    t = ms("2026-10-16")
    svc.raw("""MATCH (s:System {id:'event-bus'}), (p:Person {id:'aisha'})
               CREATE (d:Decision {id:'D-LIVE', summary:'Move event bus from Kafka to Redis Streams', valid_from:$t, valid_to:null, recorded_at:$t, confidence:0.9})
               CREATE (c:Claim {id:'C-LIVE', text:'The event bus runs on Redis Streams.', valid_from:$t, valid_to:null, recorded_at:$t})
               CREATE (d)-[:AFFECTS]->(s), (d)-[:DECIDED_BY]->(p), (d)-[:ESTABLISHES]->(c), (c)-[:ABOUT]->(s)""", {"t": t})
    svc.run("supersede", new_id="D-LIVE", old_id="D-07")


def test_live_kafka_reversal_yields_three_docs_two_tickets_with_owners(svc):
    _apply_live_reversal(svc)
    items = brain.whats_stale(svc, "D-LIVE")
    assert {i["item_id"] for i in items if i["item_label"] == "Doc"} == {"DOC-event-bus-readme", "DOC-onboarding", "ADR-011"}
    assert len([i for i in items if i["item_label"] == "Ticket"]) == 2
    assert all(i["owner_id"] for i in items)
    adr = next(i for i in items if i["item_id"] == "ADR-011")
    assert adr["owner_id"] == "omar" and "Platform team" in adr["routed_via"]
    # history is kept: the old decision still exists, closed at the new decision's start
    old = svc.raw("MATCH (d:Decision {id:'D-07'}) RETURN d.valid_to").result_set[0][0]
    assert old == ms("2026-10-16")
