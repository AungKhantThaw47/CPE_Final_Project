// Combined history linkage view for DeploymentHash + FolderHash.
// Graph view: component latest hash, output dependency linkage, and the latest folder hash for each folder path.
MATCH (component)
WHERE component:CloudRunJob OR component:CloudRunService
MATCH componentHashLink=(component)-[:HAS_HASH]->(latestDep:DeploymentHash)
OPTIONAL MATCH (latestFolder:FolderHash)
WHERE NOT EXISTS {
    MATCH (:FolderHash)-[:PREVIOUS_FOLDER_HASH]->(latestFolder)
}
OPTIONAL MATCH producedLink=(latestFolder)-[:PRODUCED_BY]->(producerDep:DeploymentHash)
OPTIONAL MATCH producerComponentLink=(producerComponent)-[:HAS_HASH]->(producerDep)
WHERE producerComponent:CloudRunJob OR producerComponent:CloudRunService
OPTIONAL MATCH dependsOnLink=(latestFolder)-[:DEPENDS_ON_DATA_FROM]->(srcFolder:FolderHash)
OPTIONAL MATCH bucketLink=(bucket:StorageBucket)-[:HAS_HASH]->(latestFolder)
RETURN componentHashLink, producedLink, producerComponentLink, dependsOnLink, bucketLink, component, latestDep, producerComponent, producerDep, latestFolder, srcFolder, bucket
ORDER BY component.name, bucket.name, latestFolder.folder_path;
