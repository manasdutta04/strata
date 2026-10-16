// Q3 supersede: close the old decision and its claims at the new decision's start. Nothing is deleted.
MATCH (new:Decision {id: $new_id}), (old:Decision {id: $old_id})
SET old.valid_to = new.valid_from
MERGE (new)-[:SUPERSEDES {ts: new.valid_from}]->(old)
WITH old, new
OPTIONAL MATCH (old)-[:ESTABLISHES]->(c:Claim) WHERE c.valid_to IS NULL
SET c.valid_to = new.valid_from
RETURN old.id AS old_id, new.id AS new_id, collect(c.id) AS closed_claims
