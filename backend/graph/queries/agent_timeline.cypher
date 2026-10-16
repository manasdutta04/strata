// agent_timeline: creation and handoff events for every task, oldest first, for the Agents timeline.
MATCH (t:Task)
OPTIONAL MATCH (t)-[h:HANDED_TO]->(a:Agent)
OPTIONAL MATCH (c:Agent)-[:CREATED]->(t)
RETURN t.id AS task_id, t.kind AS kind, t.status AS status, c.name AS created_by, t.created_at AS created_at,
       collect(CASE WHEN a IS NULL THEN NULL ELSE {agent: a.name, ts: h.ts} END) AS handoffs
ORDER BY t.created_at, t.id
