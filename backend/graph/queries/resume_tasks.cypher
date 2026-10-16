// Q11 resume_tasks: open or in-progress tasks, their agents and causing decision, so work resumes after a restart.
MATCH (t:Task) WHERE t.status IN ['open', 'in_progress']
OPTIONAL MATCH (t)-[:HANDED_TO]->(a:Agent)
OPTIONAL MATCH (t)-[:CAUSED_BY]->(d:Decision)
RETURN t.id AS task_id, t.kind AS kind, t.status AS status, d.id AS decision_id, t.created_at AS created_at, collect(a.name) AS agents
ORDER BY created_at
