// Resolve latest hash for an upstream component.
// Use this in services/jobs to pick the source hash folder.
// Replace the value below with your desired upstream component key.
MATCH (c {key: "job:dvb-text-cleaner-job"})-[:HAS_HASH]->(h:DeploymentHash)
RETURN c.key AS source_component, h.hash_value AS latest_hash;
