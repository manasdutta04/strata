// approve_doc: approving a drift task creates a new version on top of the latest version of the Doc. It asserts the new claim
// and keeps every claim / citation of the previous version that is still in force; the old version is kept.
MATCH (t:Task {id: $task_id, status: 'open'})-[:CONCERNS]->(orig:Doc), (t)-[:CAUSED_BY]->(d:Decision)-[:ESTABLISHES]->(c:Claim)
MATCH (orig)-[:NEXT_VERSION*0..10]->(old:Doc) WHERE NOT (old)-[:NEXT_VERSION]->()
CREATE (new:Doc {id: $new_id, title: old.title, url: old.url, kind: old.kind, version: old.version + 1, updated_at: $now, change_note: t.draft})
CREATE (old)-[:NEXT_VERSION]->(new), (new)-[:ASSERTS]->(c)
SET t.status = 'approved', t.updated_at = $now
RETURN new.id AS new_id, old.id AS old_id
