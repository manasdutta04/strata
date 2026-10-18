// system_owner: the team that owns a system and its members (accountability at the system level).
MATCH (s:System {id: $system_id})<-[:OWNS]-(t:Team)
OPTIONAL MATCH (t)<-[:MEMBER_OF]-(m:Person)
RETURN t.id AS team_id, t.name AS team, collect({id: m.id, name: m.name, role: m.role}) AS members
