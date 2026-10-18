// item_text: title and chunk text of a Doc or Ticket (from its earliest version on), plus fixes already applied to it,
// used by the Steward to draft a fix.
MATCH (i {id: $item_id})
OPTIONAL MATCH (v)-[:NEXT_VERSION*0..10]->(i)
OPTIONAL MATCH (v)-[:HAS_CHUNK]->(c:Chunk)
RETURN i.title AS title, collect(DISTINCT c.text) AS chunks, [n IN collect(DISTINCT v.change_note) WHERE n IS NOT NULL] AS changes
