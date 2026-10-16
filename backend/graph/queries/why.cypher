// Q2 why: the decision in force for a system as of time $t, who decided, what it superseded (lineage), what replaced it later, and evidence.
MATCH (s:System {id: $system_id})<-[:AFFECTS]-(d:Decision)
WHERE d.valid_from <= $t AND (d.valid_to IS NULL OR d.valid_to > $t)
OPTIONAL MATCH (d)-[:DECIDED_BY]->(p:Person)
OPTIONAL MATCH (d)-[:EVIDENCED_BY]->(ev) WHERE NOT ev:Chunk
OPTIONAL MATCH (newer:Decision)-[:SUPERSEDES]->(d)
OPTIONAL MATCH lineage = (d)-[:SUPERSEDES*1..5]->(old:Decision)
RETURN d.id AS decision_id, d.summary AS summary, d.rationale AS rationale, d.valid_from AS valid_from, d.valid_to AS valid_to,
       p.id AS decided_by, p.name AS decided_by_name,
       collect(DISTINCT {id: ev.id, kind: labels(ev)[0], text: coalesce(ev.text, ev.title)}) AS evidence,
       collect(DISTINCT {id: newer.id, summary: newer.summary, valid_from: newer.valid_from}) AS superseded_by,
       collect(DISTINCT [n IN nodes(lineage) | n.id]) AS lineage
