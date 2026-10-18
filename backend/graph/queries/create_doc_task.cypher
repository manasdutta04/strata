// create_doc_task: the coordination Task for checking one new doc; agents hand it to each other through the graph.
MATCH (a:Agent {name: 'Ingestor'}), (d:Doc {id: $doc_id})
CREATE (t:Task {id: $task_id, kind: 'doc_check', status: 'in_progress', draft: $title, created_by_agent: 'Ingestor', created_at: $now, updated_at: $now})
CREATE (a)-[:CREATED]->(t), (t)-[:CONCERNS]->(d)
RETURN t.id AS task_id
