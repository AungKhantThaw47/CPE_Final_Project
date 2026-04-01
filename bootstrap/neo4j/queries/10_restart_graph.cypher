// Restart graph state by removing all nodes and relationships.
// Use with caution: this clears the entire database content.
MATCH (n)
DETACH DELETE n;
