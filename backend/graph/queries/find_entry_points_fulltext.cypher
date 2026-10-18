// Q1b find_entry_points (keyword): full-text (stemmed, scored) matches for one term over chunk text, with the doc/message each belongs to.
// Fused with Q1a so a plain keyword like "deploy" always finds the runbook even when embeddings are far apart.
CALL db.idx.fulltext.queryNodes('Chunk', $terms) YIELD node, score
MATCH (src)-[:HAS_CHUNK]->(node)
RETURN src.id AS src_id, labels(src)[0] AS src_label, node.id AS chunk_id, node.text AS text, score
ORDER BY score DESC LIMIT 20
