// item_text: title and chunk text of a Doc or Ticket, used by the Steward to draft a fix.
MATCH (i {id: $item_id})
OPTIONAL MATCH (i)-[:HAS_CHUNK]->(c:Chunk)
RETURN i.title AS title, collect(c.text) AS chunks
