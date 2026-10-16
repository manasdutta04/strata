// p_record_shown: personal memory: which decision version a question was shown.
MATCH (q:Question {id: $qid})
CREATE (q)-[:SHOWN]->(:DecisionRef {decision_id: $decision_id, system_id: $system_id, valid_from_at_time: $valid_from})
