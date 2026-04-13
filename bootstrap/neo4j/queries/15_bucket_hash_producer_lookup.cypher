// Show folder hashes and the deployment hash that produced each one.
// This uses hash equality so it works even before the PRODUCED_BY relationship has been backfilled.
MATCH (bucket:StorageBucket)-[:HAS_HASH]->(folderHash:FolderHash)
OPTIONAL MATCH (deploymentHash:DeploymentHash)
WHERE deploymentHash.hash_value = folderHash.hash_value
RETURN bucket.key AS bucket_key,
       bucket.name AS bucket_name,
    folderHash.folder_path AS folder_path,
    folderHash.hash_value AS folder_hash,
    deploymentHash.component_kind AS component_kind,
    deploymentHash.component_name AS component_name,
    deploymentHash.hash_value AS deployment_hash,
    deploymentHash.deployment_source AS deployment_source,
    deploymentHash.updater AS updater,
    deploymentHash.deployment_ref AS deployment_ref
ORDER BY bucket_name, folder_path, component_kind, component_name;