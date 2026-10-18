// doc_check: every claim a doc asserts, whether it is still true, and (if not) the decision that closed it and who made it.
// This is the write-time contradiction check: wrong knowledge is caught before anyone follows it.
MATCH (d:Doc {id: $doc_id})-[r:ASSERTS]->(c:Claim)
OPTIONAL MATCH (old:Decision)-[:ESTABLISHES]->(c)
OPTIONAL MATCH (new:Decision)-[:SUPERSEDES]->(old) WHERE c.valid_to IS NOT NULL
OPTIONAL MATCH (new)-[:DECIDED_BY]->(p:Person)
RETURN c.id AS claim_id, c.text AS claim_text, r.quote AS quote, c.valid_to IS NULL AS in_force,
       old.id AS established_by, new.id AS closed_by, new.summary AS closed_by_summary, new.valid_from AS closed_at, p.name AS closed_by_name
ORDER BY in_force, claim_id
