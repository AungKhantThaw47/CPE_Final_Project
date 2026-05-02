#!/usr/bin/env python3
"""Check pending_review_annotation folder connections in Neo4j."""

import os
from neo4j import GraphDatabase


def check_pending_annotation_connections():
    """Query Neo4j directly to check pending_review_annotation folder connections."""
    
    # Connection parameters
    neo4j_uri = os.environ.get("NEO4J_URI", "neo4j+s://4a6a2b6a.databases.neo4j.io")
    neo4j_user = os.environ.get("NEO4J_USER", "4a6a2b6a")
    neo4j_password = os.environ.get("NEO4J_PASSWORD", "5C_VdJn2ERjV_4ftwy3a0tWyLmv4cd93V871d-uxELM")
    neo4j_database = os.environ.get("NEO4J_DATABASE", "4a6a2b6a")
    
    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    
    try:
        with driver.session(database=neo4j_database) as session:
            # First, check if ANY pending_review_annotation folder exists
            print("=== Checking if pending_review_annotation folders exist ===\n")
            
            count_query = """
MATCH (f:FolderHash {folder_path: "pending_review_annotation/"})
RETURN count(f) as count
            """
            
            count_result = session.run(count_query).single()
            count = count_result['count'] if count_result else 0
            print(f"Total pending_review_annotation folder nodes: {count}\n")
            
            if count == 0:
                print("No pending_review_annotation folders found in database!")
                print("Checking what folder paths exist:\n")
                
                folders_query = """
MATCH (f:FolderHash)
RETURN DISTINCT f.folder_path
ORDER BY f.folder_path
LIMIT 20
                """
                
                folders = session.run(folders_query)
                print("Sample folder paths:")
                for record in folders:
                    print(f"  - {record['f.folder_path']}")
                return
            
            # Now check the latest one with all connections
            print("=== Checking latest pending_review_annotation folder ===\n")
            
            query = """
MATCH (paFolder:FolderHash {folder_path: "pending_review_annotation/"})
WHERE NOT EXISTS {
    MATCH (:FolderHash)-[:PREVIOUS_FOLDER_HASH]->(paFolder)
}
OPTIONAL MATCH bucketToFolder=(bucket:StorageBucket)-[:HAS_HASH]->(paFolder)
OPTIONAL MATCH folderToBucket=(paFolder)-[:HAS_HASH]->(bucket2:StorageBucket)
OPTIONAL MATCH producedPath=(paFolder)-[:PRODUCED_BY]->(producerDep:DeploymentHash)
OPTIONAL MATCH producerCompPath=(producerComp)-[:HAS_HASH]->(producerDep)
  WHERE producerComp:CloudRunJob OR producerComp:CloudRunService
OPTIONAL MATCH dependsPath=(paFolder)-[:DEPENDS_ON_DATA_FROM]->(depFolder:FolderHash)
OPTIONAL MATCH dependedByPath=(dependingFolder:FolderHash)-[:DEPENDS_ON_DATA_FROM]->(paFolder)
RETURN paFolder,
       bucket, bucket2,
       producerDep, producerComp,
       depFolder, dependingFolder,
       bucketToFolder, folderToBucket, producedPath, dependsPath, dependedByPath, producerCompPath
            """
            
            result = session.run(query)
            records = list(result)
            
            if not records:
                print("No LATEST pending_review_annotation folder found!")
                print("(This means there are pending_review_annotation nodes but none is marked as latest)")
                return
            
            print(f"Found {len(records)} record(s)\n")
            
            for i, record in enumerate(records):
                print(f"=== Record {i+1} ===")
                print(f"Folder: {record['paFolder']}")
                print(f"\nBucket connections:")
                print(f"  bucket (StorageBucket)-[:HAS_HASH]->(folder): {record['bucket']}")
                print(f"  folder-[:HAS_HASH]->(bucket2): {record['bucket2']}")
                print(f"\nProducer:")
                print(f"  producerDep: {record['producerDep']}")
                print(f"  producerComp: {record['producerComp']}")
                print(f"\nDependencies:")
                print(f"  depFolder (depends on): {record['depFolder']}")
                print(f"  dependingFolder (depends on this): {record['dependingFolder']}")
                print(f"\nPaths found:")
                print(f"  bucketToFolder: {record['bucketToFolder'] is not None}")
                print(f"  folderToBucket: {record['folderToBucket'] is not None}")
                print(f"  producedPath: {record['producedPath'] is not None}")
                print(f"  dependsPath: {record['dependsPath'] is not None}")
                print(f"  dependedByPath: {record['dependedByPath'] is not None}")
                print(f"  producerCompPath: {record['producerCompPath'] is not None}")
                print()
    
    finally:
        driver.close()


if __name__ == "__main__":
    check_pending_annotation_connections()
