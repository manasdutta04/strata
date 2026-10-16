// person_collab_teams: which teams a person's collaborators belong to (explains a knowledge bridge).
MATCH (p:Person {id: $person_id})-[c:COLLABORATES]->(o:Person)-[:MEMBER_OF]->(t:Team)
RETURN t.name AS team, count(DISTINCT o) AS people, sum(c.weight) AS weight
ORDER BY weight DESC
