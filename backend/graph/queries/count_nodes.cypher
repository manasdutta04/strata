// count_nodes: next-id helper for generated Decision/Claim ids.
MATCH (d:Decision) WITH count(d) AS decisions
MATCH (c:Claim) RETURN decisions, count(c) AS claims
