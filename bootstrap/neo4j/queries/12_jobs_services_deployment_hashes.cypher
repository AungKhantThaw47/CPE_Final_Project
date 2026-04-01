// Show both jobs and services with their latest deployment hashes.
// Graph output for Neo4j Browser Explore/Graph view.
MATCH (c)
WHERE c:CloudRunJob OR c:CloudRunService
OPTIONAL MATCH (c)-[h:HAS_HASH]->(latest:DeploymentHash)
RETURN c, h, latest;
