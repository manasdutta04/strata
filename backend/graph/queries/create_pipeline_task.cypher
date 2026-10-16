// create_pipeline_task: the coordination Task for one ingest run; agents hand it to each other through the graph.
MATCH (a:Agent {name: 'Ingestor'}), (d:Decision {id: $decision_id})
CREATE (t:Task {id: $task_id, kind: 'review', status: 'in_progress', draft: $summary, created_by_agent: 'Ingestor', created_at: $now, updated_at: $now})
CREATE (a)-[:CREATED]->(t), (t)-[:CAUSED_BY]->(d)
RETURN t.id AS task_id
