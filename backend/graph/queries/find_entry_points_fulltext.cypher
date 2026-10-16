// Q1b find_entry_points (keyword): full-text match on doc titles.
CALL db.idx.fulltext.queryNodes('Doc', $q) YIELD node, score
RETURN node.id AS id, node.title AS title, score ORDER BY score DESC LIMIT 5
