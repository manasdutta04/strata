// people_full: every person with role and team (resolves names in questions).
MATCH (p:Person)-[:MEMBER_OF]->(t:Team)
RETURN p.id AS id, p.name AS name, p.role AS role, t.name AS team
