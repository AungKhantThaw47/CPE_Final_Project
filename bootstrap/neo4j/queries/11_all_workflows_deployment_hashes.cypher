// Show pipeline components and latest deployment hashes for all workflows.
// Similar to 09_pipeline_deployment_hashes.cypher, but not limited to daily-pipeline.
MATCH (w:Workflow)-[o:ORCHESTRATES]->(c:SystemNode)
WITH w, c, o
ORDER BY w.name, o.step_order
OPTIONAL MATCH (c)-[h:HAS_HASH]->(latest:DeploymentHash)
RETURN w, c, o, h, latest;
