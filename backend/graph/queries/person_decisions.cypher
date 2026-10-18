// person_decisions: decisions a person made, the system each affects, and whether it is still in force.
MATCH (d:Decision)-[:DECIDED_BY]->(p:Person {id: $person_id}), (d)-[:AFFECTS]->(s:System)
OPTIONAL MATCH (newer:Decision)-[:SUPERSEDES]->(d)
RETURN d.id AS id, d.summary AS summary, d.valid_from AS valid_from, d.valid_to AS valid_to, s.id AS system_id, newer.id AS superseded_by
ORDER BY valid_from DESC
