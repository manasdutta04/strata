// p_last_shown: latest decision version shown to this user per system, with the question that showed it.
MATCH (q:Question)-[:SHOWN]->(r:DecisionRef)
WITH r.system_id AS system_id, q, r ORDER BY q.ts DESC
RETURN system_id, collect(r.decision_id)[0] AS decision_id, collect(q.text)[0] AS question, max(q.ts) AS last_ts
