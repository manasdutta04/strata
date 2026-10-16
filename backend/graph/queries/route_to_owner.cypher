// Q5 route_to_owner: direct owner if any; otherwise the owning team of the item's system (caller picks top expert via who_knows).
MATCH (item {id: $item_id})
OPTIONAL MATCH (owner:Person)-[:OWNS]->(item)
OPTIONAL MATCH (item)-[:ABOUT]->(s:System)<-[:OWNS]-(t:Team)<-[:MEMBER_OF]-(m:Person)
RETURN owner.id AS owner_id, owner.name AS owner_name, s.id AS system_id, t.name AS team,
       collect(DISTINCT m.id) AS team_member_ids
