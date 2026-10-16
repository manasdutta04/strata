// graph_view: decision/claim/doc/ticket/evidence structure for the graph panel; the UI dims anything closed or not yet true as of the chosen time.
MATCH (a)-[r:AFFECTS|DECIDED_BY|SUPERSEDES|ESTABLISHES|ASSERTS|CITES|NEXT_VERSION|EVIDENCED_BY]->(b)
WHERE NOT a:Chunk AND NOT b:Chunk AND NOT (a:Claim AND type(r) = 'EVIDENCED_BY')
RETURN a.id AS src, labels(a)[0] AS src_label, coalesce(a.title, a.summary, a.text, a.name) AS src_name, a.valid_from AS src_from, a.valid_to AS src_to, a.status AS src_status,
       b.id AS dst, labels(b)[0] AS dst_label, coalesce(b.title, b.summary, b.text, b.name) AS dst_name, b.valid_from AS dst_from, b.valid_to AS dst_to, b.status AS dst_status,
       type(r) AS type, r.ts AS ts
