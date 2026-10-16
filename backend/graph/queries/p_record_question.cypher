// p_record_question: personal memory (graph strata_user_<id>): a session asked a question.
MERGE (s:Session {id: $sid}) ON CREATE SET s.started_at = $now
CREATE (q:Question {id: $qid, text: $text, ts: $now})
CREATE (s)-[:ASKED]->(q)
