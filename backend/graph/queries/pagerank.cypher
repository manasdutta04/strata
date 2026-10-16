// Q7b PageRank over the collaboration graph: who the organisation's work flows through.
CALL algo.pageRank('Person', 'COLLABORATES') YIELD node, score
RETURN node.id AS person_id, score ORDER BY score DESC
