// drift_audit: every current Doc / open Ticket that still asserts a closed claim or cites a superseded decision, the decision
// that made it wrong, and the drift task tracking it (if any). This is the brain auditing itself, not just reacting to new messages.
MATCH (new:Decision)-[:SUPERSEDES]->(old:Decision)
MATCH (item)-[r:ASSERTS|CITES]->(x)
WHERE (x = old OR (old)-[:ESTABLISHES]->(x)) AND NOT (item)-[:NEXT_VERSION]->()
  AND (item:Doc OR (item:Ticket AND item.status = 'open'))
OPTIONAL MATCH (t:Task {kind: 'drift_fix'})-[:CONCERNS]->(item)
WHERE (t)-[:CAUSED_BY]->(new)
RETURN item.id AS item_id, labels(item)[0] AS item_label, item.title AS title, type(r) AS how,
       coalesce(x.text, x.summary) AS stale_text, new.id AS decision_id, new.summary AS decision_summary,
       new.valid_from AS decided_at, t.id AS task_id, t.status AS task_status
ORDER BY decided_at DESC, item_label, item_id
