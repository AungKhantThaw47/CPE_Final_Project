#!/usr/bin/env python3
"""Verify the correct dependency chain in Neo4j."""

import os
from neo4j import GraphDatabase


def check_dependency_chain():
    """Query Neo4j to verify the dependency chain."""
    
    neo4j_uri = os.environ.get("NEO4J_URI", "neo4j+s://4a6a2b6a.databases.neo4j.io")
    neo4j_user = os.environ.get("NEO4J_USER", "4a6a2b6a")
    neo4j_password = os.environ.get("NEO4J_PASSWORD", "5C_VdJn2ERjV_4ftwy3a0tWyLmv4cd93V871d-uxELM")
    neo4j_database = os.environ.get("NEO4J_DATABASE", "4a6a2b6a")
    
    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    
    try:
        with driver.session(database=neo4j_database) as session:
            print("=== Verifying Dependency Chain ===\n")
            
            # Chain: events → annotated_articles → pending_review_annotation → crisis_articles
            chain = [
                ("events/", "annotated_articles/"),
                ("annotated_articles/", "pending_review_annotation/"),
                ("pending_review_annotation/", "crisis_articles/"),
            ]
            
            for i, (from_folder, to_folder) in enumerate(chain, 1):
                print(f"Step {i}: {from_folder} → {to_folder}")
                
                query = f"""
MATCH (fromFolder:FolderHash {{folder_path: "{from_folder}"}})
WHERE NOT EXISTS {{
    MATCH (:FolderHash)-[:PREVIOUS_FOLDER_HASH]->(fromFolder)
}}
OPTIONAL MATCH (fromFolder)-[dep:DEPENDS_ON_DATA_FROM]->(toFolder:FolderHash {{folder_path: "{to_folder}"}})
WHERE NOT EXISTS {{
    MATCH (:FolderHash)-[:PREVIOUS_FOLDER_HASH]->(toFolder)
}}
RETURN fromFolder.hash_value as from_hash,
       toFolder.hash_value as to_hash,
       dep is not null as dependency_exists,
       type(dep) as relationship_type
                """
                
                result = session.run(query)
                records = list(result)
                
                if not records:
                    print(f"  ❌ {from_folder} folder not found or latest version missing\n")
                else:
                    for record in records:
                        if record['dependency_exists']:
                            print(f"  ✅ Dependency exists")
                            print(f"     From hash: {record['from_hash']}")
                            print(f"     To hash: {record['to_hash']}")
                            print(f"     Relation: {record['relationship_type']}\n")
                        else:
                            print(f"  ❌ No DEPENDS_ON_DATA_FROM relationship found")
                            print(f"     From: {record['from_hash']}")
                            print(f"     To: {record['to_hash']}\n")
            
            # Also check complete chain path
            print("=== Full Chain Path Verification ===\n")
            
            query = """
MATCH (events:FolderHash {folder_path: "events/"})
WHERE NOT EXISTS { MATCH (:FolderHash)-[:PREVIOUS_FOLDER_HASH]->(events) }
MATCH (events)-[d1:DEPENDS_ON_DATA_FROM]->(annotated:FolderHash {folder_path: "annotated_articles/"})
WHERE NOT EXISTS { MATCH (:FolderHash)-[:PREVIOUS_FOLDER_HASH]->(annotated) }
MATCH (annotated)-[d2:DEPENDS_ON_DATA_FROM]->(pending:FolderHash {folder_path: "pending_review_annotation/"})
WHERE NOT EXISTS { MATCH (:FolderHash)-[:PREVIOUS_FOLDER_HASH]->(pending) }
MATCH (pending)-[d3:DEPENDS_ON_DATA_FROM]->(crisis:FolderHash {folder_path: "crisis_articles/"})
WHERE NOT EXISTS { MATCH (:FolderHash)-[:PREVIOUS_FOLDER_HASH]->(crisis) }
RETURN events.hash_value, annotated.hash_value, pending.hash_value, crisis.hash_value
            """
            
            result = session.run(query)
            records = list(result)
            
            if records:
                print("✅ COMPLETE CHAIN EXISTS!")
                for record in records:
                    print(f"  events → annotated_articles → pending_review_annotation → crisis_articles")
                    print(f"  {record[0]}")
                    print(f"  {record[1]}")
                    print(f"  {record[2]}")
                    print(f"  {record[3]}")
            else:
                print("❌ Complete chain not found in Neo4j")
                print("   This means at least one dependency link is broken or folders are missing")
    
    finally:
        driver.close()


if __name__ == "__main__":
    check_dependency_chain()
