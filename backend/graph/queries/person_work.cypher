// person_work: the concrete work items (sources) that make a person an expert on a system.
MATCH (p:Person {id: $person_id})-[r:AUTHORED|REVIEWED]->(w)-[:ABOUT]->(s:System {id: $system_id})
RETURN w.id AS id, labels(w)[0] AS kind, coalesce(w.title, w.text) AS text, w.url AS url, type(r) AS how
ORDER BY coalesce(r.ts, 0) DESC LIMIT 6
