// Q6 create_drift_task: a Task for a stale item, caused by a decision, assigned to an owner, created by the Steward agent.
MATCH (item {id: $item_id}), (d:Decision {id: $decision_id}), (p:Person {id: $owner_id}), (a:Agent {name: 'Steward'})
CREATE (t:Task {id: $task_id, kind: 'drift_fix', status: 'open', draft: $draft, created_by_agent: 'Steward', created_at: $now, updated_at: $now})
CREATE (a)-[:CREATED]->(t), (t)-[:CONCERNS]->(item), (t)-[:CAUSED_BY]->(d), (t)-[:ASSIGNED_TO]->(p)
RETURN t.id AS task_id
