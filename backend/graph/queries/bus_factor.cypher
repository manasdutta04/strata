// Q9 bus_factor: systems where at most one person has meaningful (>= threshold) authored/reviewed activity.
MATCH (s:System)<-[:ABOUT]-(w)<-[r:AUTHORED|REVIEWED]-(p:Person)
WITH s, p, count(r) AS a
WHERE a >= $threshold
WITH s, collect({id: p.id, name: p.name, activity: a}) AS experts
WHERE size(experts) <= 1
RETURN s.id AS system_id, experts
