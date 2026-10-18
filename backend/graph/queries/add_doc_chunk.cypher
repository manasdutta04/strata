// add_doc_chunk: one embedded paragraph of a doc, for retrieval and for drafting fixes.
MATCH (d:Doc {id: $doc_id})
CREATE (d)-[:HAS_CHUNK]->(:Chunk {id: $chunk_id, text: $text, source_id: $doc_id, embedding: vecf32($vec)})
