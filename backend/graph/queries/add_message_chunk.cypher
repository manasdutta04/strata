// add_message_chunk: embedded chunk of a message, linked for retrieval and as decision evidence.
MATCH (m:Message {id: $msg_id}), (d:Decision {id: $decision_id})
CREATE (m)-[:HAS_CHUNK]->(c:Chunk {id: $chunk_id, text: m.text, source_id: m.id, embedding: vecf32($vec)})
CREATE (d)-[:EVIDENCED_BY]->(c)
