// Q7a who_knows (activity): authored/reviewed work on a system, per person.
MATCH (p:Person)-[r:AUTHORED|REVIEWED]->(w)-[:ABOUT]->(s:System {id: $system_id})
RETURN p.id AS person_id, p.name AS name, count(r) AS activity,
       sum(CASE WHEN type(r) = 'AUTHORED' THEN 1 ELSE 0 END) AS authored,
       sum(CASE WHEN type(r) = 'REVIEWED' THEN 1 ELSE 0 END) AS reviewed
ORDER BY activity DESC
