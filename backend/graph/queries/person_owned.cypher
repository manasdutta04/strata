// person_owned: current docs and open tickets a person is accountable for.
MATCH (p:Person {id: $person_id})-[:OWNS]->(i)
WHERE (i:Doc OR (i:Ticket AND i.status = 'open')) AND NOT (i)-[:NEXT_VERSION]->()
RETURN i.id AS id, labels(i)[0] AS kind, i.title AS title, i.url AS url
ORDER BY kind, id
