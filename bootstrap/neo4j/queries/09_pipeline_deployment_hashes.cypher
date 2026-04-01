// Show only pipeline components and their latest deployment hash.
// Unnecessary history nodes/relations are intentionally excluded.
MATCH (:Workflow {name: "daily-pipeline"})-[o:ORCHESTRATES]->(c:SystemNode)
WITH c, o
ORDER BY o.step_order
OPTIONAL MATCH (c)-[h:HAS_HASH]->(latest:DeploymentHash)
RETURN c, h, latest;
