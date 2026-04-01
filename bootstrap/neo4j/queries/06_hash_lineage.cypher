// Show hash-level lineage (reader hash depends on writer hash) through buckets.
MATCH (reader:DeploymentHash)-[r:DEPENDS_ON_DATA_FROM]->(writer:DeploymentHash)
RETURN reader.component_name AS reader_component,
       writer.component_name AS writer_component,
       r.bucket AS via_bucket
ORDER BY reader_component, writer_component;
