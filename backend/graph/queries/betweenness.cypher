// Q7c Betweenness over the collaboration graph: people who bridge otherwise separate groups (knowledge bridges).
CALL algo.betweenness({nodeLabels: ['Person'], relationshipTypes: ['COLLABORATES']}) YIELD node, score
RETURN node.id AS person_id, score ORDER BY score DESC
