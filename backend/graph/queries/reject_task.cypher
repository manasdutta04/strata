// reject_task: the human declined the drafted fix; the item stays flagged as stale knowledge.
MATCH (t:Task {id: $task_id, status: 'open'})
SET t.status = 'rejected', t.updated_at = $now
RETURN t.id AS task_id
