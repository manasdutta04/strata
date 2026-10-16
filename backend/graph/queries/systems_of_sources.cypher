// systems_of_sources: the systems that retrieved docs/messages are about (turns entry points into a topic).
MATCH (s)-[:ABOUT]->(sys:System) WHERE s.id IN $ids
RETURN s.id AS src_id, sys.id AS system_id
