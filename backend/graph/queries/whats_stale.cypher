// Q4 whats_stale: every Doc and open Ticket that asserts a closed claim or cites the superseded decision.
MATCH (new:Decision {id: $new_id})-[:SUPERSEDES]->(old:Decision)
MATCH (item)-[r:ASSERTS|CITES]->(x)
WHERE (x = old OR (old)-[:ESTABLISHES]->(x))
  AND (item:Doc OR (item:Ticket AND item.status = 'open'))
RETURN DISTINCT item.id AS item_id, labels(item)[0] AS item_label, item.title AS title, type(r) AS how,
       x.id AS stale_id, coalesce(x.text, x.summary) AS stale_text
ORDER BY item_label, item_id
