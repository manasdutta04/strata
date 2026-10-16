// decisions_by_ids: summary, rationale, owner and evidence for a set of decisions (lineage and superseded-by).
MATCH (d:Decision) WHERE d.id IN $ids
OPTIONAL MATCH (d)-[:DECIDED_BY]->(p:Person)
OPTIONAL MATCH (d)-[:EVIDENCED_BY]->(ev) WHERE NOT ev:Chunk
RETURN d.id AS id, d.summary AS summary, d.rationale AS rationale, d.valid_from AS valid_from, d.valid_to AS valid_to,
       p.id AS decided_by, p.name AS decided_by_name,
       collect(DISTINCT {id: ev.id, kind: labels(ev)[0], text: coalesce(ev.text, ev.title), url: ev.url}) AS evidence
