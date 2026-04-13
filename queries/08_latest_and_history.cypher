// Show each component's latest hash and optional previous hash.
MATCH (c:SystemNode)-[:HAS_HASH]->(latest:DeploymentHash)
OPTIONAL MATCH (latest)-[r]->(previous:DeploymentHash)
WHERE type(r) = "PREVIOUS_HASH"
RETURN c.key AS component_key,
       c.name AS component_name,
       latest.hash_value AS latest_hash,
       latest.deployment_source AS latest_source,
       previous.hash_value AS previous_hash,
       previous.deployment_source AS previous_source
ORDER BY component_key;
