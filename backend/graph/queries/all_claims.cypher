// all_claims: every claim (in force or closed) and its system: the vocabulary a new doc's statements are matched against.
MATCH (c:Claim)-[:ABOUT]->(s:System)
RETURN c.id AS id, c.text AS text, s.id AS system_id, c.valid_to AS valid_to
ORDER BY s.id, c.id
