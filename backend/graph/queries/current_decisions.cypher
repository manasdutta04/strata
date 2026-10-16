// current_decisions: every decision still in force and the system it affects (grounds supersession detection).
MATCH (d:Decision)-[:AFFECTS]->(s:System) WHERE d.valid_to IS NULL
RETURN d.id AS id, d.summary AS summary, s.id AS system_id ORDER BY s.id
