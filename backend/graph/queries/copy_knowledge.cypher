// copy_knowledge: carry the previous version's claims and citations that are still in force onto the new version,
// so a fix for one decision does not erase what the doc says about everything else.
MATCH (old {id: $old_id})-[r:ASSERTS|CITES]->(x), (new {id: $new_id})
WHERE x.valid_to IS NULL AND NOT (new)-[]->(x)
WITH new, x, type(r) AS how
FOREACH (_ IN CASE WHEN how = 'ASSERTS' THEN [1] ELSE [] END | MERGE (new)-[:ASSERTS]->(x))
FOREACH (_ IN CASE WHEN how = 'CITES' THEN [1] ELSE [] END | MERGE (new)-[:CITES]->(x))
RETURN count(x) AS carried
