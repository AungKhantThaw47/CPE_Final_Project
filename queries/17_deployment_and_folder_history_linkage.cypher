// Combined history linkage view for DeploymentHash + FolderHash.
// 1) Graph view: component latest hash and history chain, plus produced folder hash and its history chain.
MATCH (component)
WHERE component:CloudRunJob OR component:CloudRunService
MATCH (component)-[:HAS_HASH]->(latestDep:DeploymentHash)
OPTIONAL MATCH depChain=(latestDep)-[:PREVIOUS_HASH*1..]->(:DeploymentHash)
OPTIONAL MATCH produced=(outFolder:FolderHash)-[:PRODUCED_BY]->(latestDep)
OPTIONAL MATCH folderChain=(outFolder)-[:PREVIOUS_FOLDER_HASH*1..]->(:FolderHash)
OPTIONAL MATCH bucketLink=(bucket:StorageBucket)-[:HAS_HASH]->(outFolder)
RETURN component, latestDep, outFolder, bucket, depChain, produced, folderChain, bucketLink
ORDER BY component.name;

// 2) Table view: latest/current and previous hashes for both deployment and folder hash families.
MATCH (component)
WHERE component:CloudRunJob OR component:CloudRunService
MATCH (component)-[:HAS_HASH]->(latestDep:DeploymentHash)
OPTIONAL MATCH (latestDep)-[:PREVIOUS_HASH]->(prevDep:DeploymentHash)
OPTIONAL MATCH (outFolder:FolderHash)-[:PRODUCED_BY]->(latestDep)
OPTIONAL MATCH (outFolder)-[:PREVIOUS_FOLDER_HASH]->(prevFolder:FolderHash)
OPTIONAL MATCH (bucket:StorageBucket)-[:HAS_HASH]->(outFolder)
RETURN component.key AS component_key,
       component.name AS component_name,
       labels(component)[0] AS component_type,
       latestDep.hash_value AS latest_deployment_hash,
       latestDep.hash_type AS latest_deployment_hash_type,
       prevDep.hash_value AS previous_deployment_hash,
       outFolder.bucket_name AS bucket_name,
       outFolder.folder_path AS folder_path,
       outFolder.hash_value AS latest_folder_hash,
       prevFolder.hash_value AS previous_folder_hash,
       CASE WHEN prevDep IS NULL THEN false ELSE true END AS has_deployment_history,
       CASE WHEN prevFolder IS NULL THEN false ELSE true END AS has_folder_history
ORDER BY component_name, bucket_name, folder_path;
