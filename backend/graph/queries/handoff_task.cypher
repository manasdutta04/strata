// handoff_task: hand a Task to an agent (durable coordination state) and set its status.
MATCH (t:Task {id: $task_id}), (a:Agent {name: $agent})
CREATE (t)-[:HANDED_TO {ts: $now}]->(a)
SET t.status = $status, t.updated_at = $now
RETURN t.id AS task_id
