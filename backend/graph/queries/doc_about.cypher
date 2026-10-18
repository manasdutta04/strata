// doc_about: scope a doc to the system it is about.
MATCH (d:Doc {id: $doc_id}), (s:System {id: $system_id})
MERGE (d)-[:ABOUT]->(s)
