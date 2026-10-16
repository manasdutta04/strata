// copy_about: carry topic links onto a new version node.
MATCH (old {id: $old_id})-[:ABOUT]->(s:System), (new {id: $new_id})
CREATE (new)-[:ABOUT]->(s)
