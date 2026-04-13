// Visual-first query for Neo4j Browser.
// Returns graph objects so you can inspect FolderHash source lineage directly.
MATCH p_out=(out:FolderHash)-[pb:PRODUCED_BY]->(dep:DeploymentHash)
OPTIONAL MATCH p_src=(out)-[fh:DEPENDS_ON_DATA_FROM {source_relation: "folder_hash_lineage"}]->(src:FolderHash)
OPTIONAL MATCH p_prev=(out)-[:PREVIOUS_FOLDER_HASH]->(prev:FolderHash)
OPTIONAL MATCH p_dep_prev=(dep)-[:PREVIOUS_HASH]->(dep_prev:DeploymentHash)
OPTIONAL MATCH p_bucket=(bucket:StorageBucket)-[:HAS_HASH]->(out)
RETURN p_src, p_prev, p_dep_prev, p_out, p_bucket, out, dep, dep_prev, src, prev, bucket
ORDER BY out.bucket_name, out.folder_path, dep.component_name;

// Tabular version (optional): link status and source/content hash metadata.
MATCH (bucket:StorageBucket)-[:HAS_HASH]->(out:FolderHash)
MATCH (out)-[pb:PRODUCED_BY]->(dep:DeploymentHash)
OPTIONAL MATCH (out)-[fh:DEPENDS_ON_DATA_FROM {source_relation: "folder_hash_lineage"}]->(src:FolderHash)
OPTIONAL MATCH (out)-[:PREVIOUS_FOLDER_HASH]->(prev:FolderHash)
OPTIONAL MATCH (dep)-[:PREVIOUS_HASH]->(dep_prev:DeploymentHash)
RETURN bucket.name AS bucket_name,
       out.folder_path AS output_folder,
       out.hash_value AS output_hash,
       pb.source_hash AS source_hash,
       pb.content_hash AS content_hash,
       prev.hash_value AS previous_folder_hash,
       dep.component_kind AS producer_kind,
       dep.component_name AS producer_name,
       dep.hash_value AS producer_deployment_hash,
  dep_prev.hash_value AS previous_deployment_hash,
       fh.source_hash AS linked_source_hash,
       CASE
         WHEN coalesce(pb.source_hash, "") = "" THEN "root_stage_no_source"
         WHEN src IS NULL THEN "missing_source_link"
         ELSE "linked"
       END AS link_status,
       src.folder_path AS source_folder,
       src.bucket_name AS source_bucket
ORDER BY bucket_name, output_folder, producer_kind, producer_name;

// Diagnostic: only rows where source_hash exists but no source FolderHash link was found.
MATCH (out:FolderHash)-[pb:PRODUCED_BY]->(dep:DeploymentHash)
OPTIONAL MATCH (out)-[:DEPENDS_ON_DATA_FROM {source_relation: "folder_hash_lineage"}]->(src:FolderHash)
WHERE coalesce(pb.source_hash, "") <> "" AND src IS NULL
RETURN out.bucket_name AS output_bucket,
    out.folder_path AS output_folder,
    out.hash_value AS output_hash,
    pb.source_hash AS expected_source_hash,
    dep.component_name AS producer_name
ORDER BY output_bucket, output_folder;

// Tip: If Browser still shows table mode, click the "Graph" result tab.
