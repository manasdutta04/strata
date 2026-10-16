// ingest_decision: record a chat message and the Decision + Claim it establishes, with provenance back to the message.
MATCH (s:System {id: $system_id}), (p:Person {id: $author_id})
CREATE (m:Message {id: $msg_id, channel: $channel, text: $text, ts: $ts})
CREATE (d:Decision {id: $decision_id, summary: $summary, rationale: $rationale, valid_from: $ts, recorded_at: $now, confidence: $confidence})
CREATE (c:Claim {id: $claim_id, text: $claim_text, valid_from: $ts, recorded_at: $now})
CREATE (p)-[:AUTHORED {ts: $ts}]->(m), (m)-[:ABOUT]->(s)
CREATE (d)-[:DECIDED_BY]->(p), (d)-[:AFFECTS]->(s), (d)-[:ESTABLISHES]->(c), (c)-[:ABOUT]->(s)
CREATE (d)-[:EVIDENCED_BY]->(m), (c)-[:EVIDENCED_BY]->(m)
RETURN d.id AS decision_id
