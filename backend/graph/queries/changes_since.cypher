// changes_since: decisions that took effect in [$since, $until], who made them, what each replaced, and evidence. Newest first.
MATCH (d:Decision)-[:AFFECTS]->(s:System)
WHERE d.valid_from >= $since AND d.valid_from <= $until
OPTIONAL MATCH (d)-[:DECIDED_BY]->(p:Person)
OPTIONAL MATCH (d)-[:SUPERSEDES]->(old:Decision)
OPTIONAL MATCH (d)-[:EVIDENCED_BY]->(ev) WHERE NOT ev:Chunk
RETURN d.id AS decision_id, d.summary AS summary, d.valid_from AS valid_from, d.valid_to AS valid_to, s.id AS system_id,
       p.id AS decided_by, p.name AS decided_by_name, old.id AS replaced_id, old.summary AS replaced_summary,
       collect(DISTINCT {id: ev.id, kind: labels(ev)[0], text: coalesce(ev.text, ev.title), url: ev.url}) AS evidence
ORDER BY valid_from DESC
