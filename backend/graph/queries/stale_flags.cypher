// stale_flags: for retrieved sources, anything they state that is no longer true: a doc/ticket asserting a closed claim or citing
// a superseded decision, or a message / ADR that was the evidence for a superseded decision. Returns what replaced it and any newer version.
MATCH (i)-[r:ASSERTS|CITES]->(x) WHERE i.id IN $ids AND x.valid_to IS NOT NULL
OPTIONAL MATCH (od:Decision) WHERE od = x OR (od)-[:ESTABLISHES]->(x)
OPTIONAL MATCH (new:Decision)-[:SUPERSEDES]->(od)
OPTIONAL MATCH (i)-[:NEXT_VERSION*1..5]->(nv) WHERE NOT (nv)-[:NEXT_VERSION]->()
RETURN i.id AS src_id, type(r) AS how, coalesce(x.text, x.summary) AS stale_text, new.id AS new_id, new.summary AS new_summary,
       new.valid_from AS new_from, nv.id AS newer_version
UNION
MATCH (old:Decision)-[:EVIDENCED_BY]->(m) WHERE m.id IN $ids AND (m:Message OR m:Doc) AND old.valid_to IS NOT NULL
OPTIONAL MATCH (new:Decision)-[:SUPERSEDES]->(old)
RETURN m.id AS src_id, 'EVIDENCE_FOR' AS how, old.summary AS stale_text, new.id AS new_id, new.summary AS new_summary,
       new.valid_from AS new_from, null AS newer_version
