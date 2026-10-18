// doc_asserts: the doc states a known claim; the quoted sentence is kept on the edge as provenance.
MATCH (d:Doc {id: $doc_id}), (c:Claim {id: $claim_id})
MERGE (d)-[r:ASSERTS]->(c)
SET r.quote = $quote
