// approve_doc: approving a drift task creates a new Doc version that asserts the new claim; the old version is kept.
MATCH (t:Task {id: $task_id, status: 'open'})-[:CONCERNS]->(old:Doc), (t)-[:CAUSED_BY]->(d:Decision)-[:ESTABLISHES]->(c:Claim)
WHERE NOT (old)-[:NEXT_VERSION]->()
CREATE (new:Doc {id: $new_id, title: old.title, url: old.url, kind: old.kind, version: old.version + 1, updated_at: $now, change_note: t.draft})
CREATE (old)-[:NEXT_VERSION]->(new), (new)-[:ASSERTS]->(c)
SET t.status = 'approved', t.updated_at = $now
RETURN new.id AS new_id
