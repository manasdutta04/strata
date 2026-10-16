// stale_reason: the graph path that makes a task's item stale (item -> closed claim / superseded decision).
MATCH (t:Task {id: $task_id})-[:CONCERNS]->(item)-[r:ASSERTS|CITES]->(x), (t)-[:CAUSED_BY]->(new:Decision)-[:SUPERSEDES]->(old:Decision)
WHERE x = old OR (old)-[:ESTABLISHES]->(x)
RETURN item.id AS item_id, type(r) AS how, x.id AS stale_id, coalesce(x.text, x.summary) AS stale_text, old.id AS old_decision_id, new.id AS new_decision_id
