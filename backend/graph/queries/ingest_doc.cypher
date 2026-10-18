// ingest_doc: a new Doc written by a person, who owns it (so a fix routes back to the author).
MATCH (p:Person {id: $author_id})
CREATE (d:Doc {id: $doc_id, title: $title, kind: $kind, version: 1, updated_at: $now})
CREATE (p)-[:AUTHORED {ts: $now}]->(d), (p)-[:OWNS]->(d)
RETURN d.id AS doc_id
