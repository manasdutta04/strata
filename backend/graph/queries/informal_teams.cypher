// Q8 informal_teams: label-propagation communities of people who really work together (vs the org chart).
CALL algo.labelPropagation({nodeLabels: ['Person'], relationshipTypes: ['COLLABORATES']}) YIELD node, communityId
RETURN communityId AS community, collect(node.id) AS member_ids
