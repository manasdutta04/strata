// Q11 resume_tasks: open or in-progress tasks and the agent they were last handed to, so work resumes after a restart.
MATCH (t:Task) WHERE t.status IN ['open', 'in_progress']
OPTIONAL MATCH (t)-[:HANDED_TO]->(a:Agent)
RETURN t.id AS task_id, t.kind AS kind, t.status AS status, a.name AS agent
ORDER BY t.created_at
