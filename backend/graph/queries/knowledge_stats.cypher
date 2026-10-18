// knowledge_stats: size and hygiene of the brain: decisions in force vs superseded, current docs and open tickets,
// items nobody owns, and decisions with no recorded evidence.
MATCH (d:Decision)
WITH count(d) AS decisions, sum(CASE WHEN d.valid_to IS NULL THEN 1 ELSE 0 END) AS in_force,
     sum(CASE WHEN size([(d)-[:EVIDENCED_BY]->(e) WHERE NOT e:Chunk | e]) = 0 THEN 1 ELSE 0 END) AS unevidenced
MATCH (i) WHERE (i:Doc OR (i:Ticket AND i.status = 'open')) AND NOT (i)-[:NEXT_VERSION]->()
WITH decisions, in_force, unevidenced, count(i) AS items,
     sum(CASE WHEN i:Doc THEN 1 ELSE 0 END) AS docs,
     collect(CASE WHEN size([(p:Person)-[:OWNS]->(i) | p]) = 0 THEN {id: i.id, label: labels(i)[0], title: i.title} END) AS unowned
MATCH (n) WHERE n:Message OR n:PR OR n:Chunk OR n:Person
RETURN decisions, in_force, unevidenced, items, docs, items - docs AS open_tickets, unowned,
       sum(CASE WHEN n:Message THEN 1 ELSE 0 END) AS messages, sum(CASE WHEN n:PR THEN 1 ELSE 0 END) AS prs,
       sum(CASE WHEN n:Chunk THEN 1 ELSE 0 END) AS chunks, sum(CASE WHEN n:Person THEN 1 ELSE 0 END) AS people
