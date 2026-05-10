#!/usr/bin/env python3
"""Debug script to manually run seed_folder_created_markers logic with logging."""

import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.neo4j_utils import (
    query_folder_hashes_from_neo4j_env,
    query_latest_folder_hash_from_neo4j_env,
    query_folder_hash_derived_from_source_hash_env,
    write_folder_hash_to_neo4j_env,
)

def test_seed_relationships():
    """Test creating DERIVED_FROM relationships."""
    
    gcs_bucket = "cpe-final-project-pipeline-data"
    
    print("\n" + "="*70)
    print("SEEDING DERIVED_FROM RELATIONSHIPS")
    print("="*70 + "\n")
    
    # Test pairs
    n_to_n_pairs = [
        ("crisis_articles/", "pending_review/"),
        ("annotated_articles/", "pending_review_annotation/"),
    ]
    
    for target_folder, source_folder in n_to_n_pairs:
        print(f"\n📦 Processing: {target_folder} ← {source_folder}")
        print("-" * 70)
        
        # Collect source hashes
        try:
            source_hashes = query_folder_hashes_from_neo4j_env(source_folder, gcs_bucket)
            print(f"   Source hashes found: {len(source_hashes) if source_hashes else 0}")
            if source_hashes:
                for h in source_hashes[:3]:
                    print(f"     - {h[:16]}...")
        except Exception as e:
            print(f"   ❌ Error querying source hashes: {e}")
            continue
        
        # Collect target hashes
        try:
            target_hashes = query_folder_hashes_from_neo4j_env(target_folder, gcs_bucket)
            print(f"   Target hashes found: {len(target_hashes) if target_hashes else 0}")
            if target_hashes:
                for h in target_hashes[:3]:
                    print(f"     - {h[:16]}...")
        except Exception as e:
            print(f"   ❌ Error querying target hashes: {e}")
            continue
        
        if not source_hashes:
            print(f"   ⏭️  Skipping (no source hashes)")
            continue
        
        # Try to create DERIVED_FROM for each source hash
        for index, source_hash in enumerate(source_hashes):
            target_hash = target_hashes[index] if index < len(target_hashes) else None
            
            if not target_hash:
                # Try to use latest
                try:
                    target_hash = query_latest_folder_hash_from_neo4j_env(target_folder, gcs_bucket)
                except:
                    pass
            
            if not target_hash:
                print(f"   ⏭️  Source [{index}] {source_hash[:16]}... - no target hash")
                continue
            
            print(f"\n   🔗 Creating DERIVED_FROM:")
            print(f"      target: {target_folder}{target_hash[:16]}...")
            print(f"      source: {source_folder}{source_hash[:16]}...")
            
            try:
                result = write_folder_hash_to_neo4j_env(
                    folder_path=target_folder,
                    hash_value=target_hash,
                    bucket_name=gcs_bucket,
                    source_folder_path=source_folder,
                    source_folder_hash=source_hash,
                )
                print(f"      ✅ Write result: {result}")
            except Exception as e:
                print(f"      ❌ Error: {e}")
    
    # Verify results
    print("\n\n" + "="*70)
    print("VERIFICATION")
    print("="*70 + "\n")
    
    try:
        from neo4j import GraphDatabase
        uri = os.environ.get('NEO4J_URI', '').strip()
        user = os.environ.get('NEO4J_USER', '').strip()
        password = os.environ.get('NEO4J_PASSWORD', '').strip()
        db = os.environ.get('NEO4J_DATABASE', 'neo4j').strip() or 'neo4j'
        
        if uri and user and password:
            driver = GraphDatabase.driver(uri, auth=(user, password))
            with driver.session(database=db) as session:
                # Check DERIVED_FROM relationships
                result = session.run('MATCH ()-[r:DERIVED_FROM]->() RETURN COUNT(r) as count').single()
                print(f"✅ DERIVED_FROM relationships now: {result['count']}")
                
                # List some relationships
                result = session.run('''
                    MATCH (target:FolderHash)-[:DERIVED_FROM]->(source:FolderHash)
                    RETURN target.folder_path, target.hash_value, source.folder_path, source.hash_value
                    LIMIT 10
                ''')
                print("\nRelationships:")
                for record in result:
                    print(f"  {record['target.folder_path']}{record['target.hash_value'][:12]}...")
                    print(f"    ← {record['source.folder_path']}{record['source.hash_value'][:12]}...\n")
            driver.close()
    except Exception as e:
        print(f"❌ Verification error: {e}")

if __name__ == "__main__":
    set_env = "set -a; [ -f .env ] && source .env; set +a; "
    print("Make sure to run this from the project root with environment loaded!")
    test_seed_relationships()
