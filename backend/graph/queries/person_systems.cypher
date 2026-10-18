// person_systems: the systems a person works on, ranked by authored + reviewed items, with their most recent activity up to $now.
MATCH (p:Person {id: $person_id})-[r:AUTHORED|REVIEWED]->(w)-[:ABOUT]->(s:System)
RETURN s.id AS system_id, count(r) AS activity, max(CASE WHEN r.ts <= $now THEN r.ts END) AS last_ts
ORDER BY activity DESC
