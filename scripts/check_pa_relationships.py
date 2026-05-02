#!/usr/bin/env python3
"""Check all relationships for the orphaned pending_review_annotation folder."""

import os
from neo4j import GraphDatabase


def check_all_relationships():
    """Query Neo4j to see what relationships exist for pending_review_annotation folder."""
    
    neo4j_uri = os.environ.get("NEO4J_URI", "neo4j+s://4a6a2b6a.databases.neo4j.io")
    neo4j_user = os.environ.get("NEO4J_USER", "4a6a2b6a")
    neo4j_password = os.environ.get("NEO4J_PASSWORD", "5C_VdJn2ERjV_4ftwy3a0tWyLmv4cd93V871d-uxELM")
    neo4j_database = os.environ.get("NEO4J_DATABASE", "4a6a2b6a")
    
    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    
    try:
        with driver.session(database=neo4j_database) as session:
            print("=== All relationships for pending_review_annotation/ ===\n")
            
            query = """
MATCH (f:FolderHash {folder_path: "pending_review_annotation/"})
WHERE NOT EXISTS {
    MATCH (:FolderHash)-[:PREVIOUS_FOLDER_HASH]->(f)
}
MATCH (f)-[r]-(connected)
RETURN type(r) as relationship_type, labels(connected) as connected_labels, connected.key as connected_key, 
       connected.name as connected_name, connected.folder_path as folder_path
ORDER BY type(r)
            """
            
            result = session.run(query)
            records = list(result)
            
            if not records:
                print("No relationships found for this folder!")
                print("\nThis folder is completely orphaned in the graph.")
                return
            
            print(f"Found {len(records)} relationship(s):\n")
            
            for record in records:
                rel_type = record['relationship_type']
                connected_labels = record['connected_labels']
                connected_key = record['connected_key']
                connected_name = record['connected_name']
                folder_path = record['folder_path']
                
                print(f"[{rel_type}] → {connected_labels}")
                if connected_key:
                    print(f"  key: {connected_key}")
                if connected_name:
                    print(f"  name: {connected_name}")
                if folder_path:
                    print(f"  folder_path: {folder_path}")
                print()
    
    finally:
        driver.close()


if __name__ == "__main__":
    check_all_relationships()
