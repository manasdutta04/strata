// current_items: the latest version of every Doc and Ticket (titles are matched in Python to resolve "the onboarding doc").
MATCH (i) WHERE (i:Doc OR i:Ticket) AND NOT (i)-[:NEXT_VERSION]->()
RETURN i.id AS id, labels(i)[0] AS label, i.title AS title, i.status AS status, i.url AS url
