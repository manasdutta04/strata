// drift_since: drift tasks opened or resolved in [$since, $until]: the item, the decision that made it wrong, the owner and the outcome.
MATCH (t:Task {kind: 'drift_fix'})-[:CONCERNS]->(item), (t)-[:CAUSED_BY]->(d:Decision), (t)-[:ASSIGNED_TO]->(p:Person)
WHERE t.updated_at >= $since AND t.updated_at <= $until
RETURN t.id AS task_id, t.status AS status, t.updated_at AS updated_at, item.id AS item_id, labels(item)[0] AS item_label,
       item.title AS item_title, d.id AS decision_id, p.name AS owner_name
ORDER BY updated_at DESC
