// copy_owner: carry ownership onto a new version node.
MATCH (p:Person)-[:OWNS]->(old {id: $old_id}), (new {id: $new_id})
CREATE (p)-[:OWNS]->(new)
