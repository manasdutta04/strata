// inbox: drift tasks with the stale item, causing decision, replaced decision and accountable owner.
MATCH (t:Task {kind: 'drift_fix'})-[:CONCERNS]->(item), (t)-[:CAUSED_BY]->(d:Decision), (t)-[:ASSIGNED_TO]->(p:Person)
OPTIONAL MATCH (d)-[:SUPERSEDES]->(old:Decision)
RETURN t.id AS task_id, t.status AS status, t.draft AS draft, t.updated_at AS updated_at,
       item.id AS item_id, labels(item)[0] AS item_label, item.title AS item_title,
       d.id AS decision_id, d.summary AS decision_summary,
       old.id AS old_decision_id, old.summary AS old_summary,
       p.id AS owner_id, p.name AS owner_name
ORDER BY t.created_at, t.id
