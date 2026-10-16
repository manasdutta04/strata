// Q1a find_entry_points (semantic): top-k chunks nearest the question vector, with the doc/message each belongs to.
CALL db.idx.vector.queryNodes('Chunk', 'embedding', 8, vecf32($qvec)) YIELD node, score
MATCH (src)-[:HAS_CHUNK]->(node)
RETURN src.id AS src_id, labels(src)[0] AS src_label, node.id AS chunk_id, node.text AS text, score
ORDER BY score
