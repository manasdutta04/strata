// team_of: team name for a person (bridge explanation).
MATCH (p:Person {id: $person_id})-[:MEMBER_OF]->(t:Team) RETURN t.name AS team
