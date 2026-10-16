// Q10 build_collaboration: derive symmetric COLLABORATES edges (both directions, weight = shared work items) after ingest.
MATCH (a:Person)-[:AUTHORED|REVIEWED]->(w)<-[:AUTHORED|REVIEWED]-(b:Person)
WHERE a.id < b.id AND NOT w:Message
WITH a, b, count(DISTINCT w) AS weight
MERGE (a)-[c:COLLABORATES]->(b) SET c.weight = weight
MERGE (b)-[c2:COLLABORATES]->(a) SET c2.weight = weight
RETURN count(*) AS pairs
