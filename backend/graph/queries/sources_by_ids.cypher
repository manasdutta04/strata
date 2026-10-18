// sources_by_ids: title/text and link of retrieved docs, tickets and messages (to quote them with a citation).
MATCH (s) WHERE s.id IN $ids
RETURN s.id AS id, labels(s)[0] AS kind, coalesce(s.title, s.text) AS title, s.url AS url
