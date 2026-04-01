// Find isolated nodes that have no incoming and no outgoing relationships.
MATCH (n:SystemNode)
WHERE NOT (n)--()
RETURN n.key AS key, labels(n) AS labels, n.name AS name
ORDER BY key;
