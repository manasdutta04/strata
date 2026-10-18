// approve_ticket: like approve_doc, for an open Ticket (new version on top of the latest one, old one kept).
MATCH (t:Task {id: $task_id, status: 'open'})-[:CONCERNS]->(orig:Ticket), (t)-[:CAUSED_BY]->(d:Decision)-[:ESTABLISHES]->(c:Claim)
MATCH (orig)-[:NEXT_VERSION*0..10]->(old:Ticket) WHERE NOT (old)-[:NEXT_VERSION]->()
CREATE (new:Ticket {id: $new_id, title: old.title, url: old.url, status: old.status, created_at: old.created_at, updated_at: $now, change_note: t.draft})
CREATE (old)-[:NEXT_VERSION]->(new), (new)-[:ASSERTS]->(c)
SET t.status = 'approved', t.updated_at = $now
RETURN new.id AS new_id, old.id AS old_id
