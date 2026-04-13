// Show jobs and services with latest deployment hash and linked hash history.
// Graph output for Neo4j Browser.
MATCH (c)
WHERE c:CloudRunJob OR c:CloudRunService
OPTIONAL MATCH (c)-[h:HAS_HASH]->(latest:DeploymentHash)
OPTIONAL MATCH p=(latest)-[:PREVIOUS_HASH*1..]->(older:DeploymentHash)
RETURN c, h, latest, p;
