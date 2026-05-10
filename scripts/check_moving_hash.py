#!/usr/bin/env python3
"""Diagnostic script to check hash relationships in Neo4j after deployment."""

import os
import sys
from pathlib import Path

# Add utils to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.neo4j_utils import (
    query_folder_hashes_from_neo4j_env,
    query_latest_folder_hash_from_neo4j_env,
    query_folder_hash_derived_from_source_hash_env,
)

def check_hash_relationships():
    """Check if DERIVED_FROM relationships exist for review stages."""
    
    print("\n" + "="*70)
    print("MOVING HASH DIAGNOSTIC - POST DEPLOYMENT CHECK")
    print("="*70 + "\n")
    
    crisis_bucket = os.environ.get('CRISIS_BUCKET', '')
    
    if not crisis_bucket:
        print("❌ CRISIS_BUCKET not set in environment")
        return
    
    print(f"📦 Crisis Bucket: {crisis_bucket}\n")
    
    # Check pending_review → crisis_articles
    print("1️⃣  CLASSIFICATION REVIEW CHAIN")
    print("-" * 70)
    
    try:
        pending_hashes = query_folder_hashes_from_neo4j_env('pending_review/', crisis_bucket)
        print(f"   Source hashes in pending_review/: {len(pending_hashes) if pending_hashes else 0}")
        if pending_hashes:
            for h in pending_hashes[:3]:
                print(f"     - {h[:16]}...")
        
        crisis_hashes = query_folder_hashes_from_neo4j_env('crisis_articles/', crisis_bucket)
        print(f"   Target hashes in crisis_articles/: {len(crisis_hashes) if crisis_hashes else 0}")
        if crisis_hashes:
            for h in crisis_hashes[:3]:
                print(f"     - {h[:16]}...")
        
        if pending_hashes:
            target = query_folder_hash_derived_from_source_hash_env(
                target_folder_path='crisis_articles/',
                source_folder_path='pending_review/',
                source_hash=pending_hashes[0],
                bucket_name=crisis_bucket,
            )
            if target:
                print(f"   ✅ DERIVED_FROM relationship found!")
                print(f"      pending_review/{pending_hashes[0][:16]}...")
                print(f"      → crisis_articles/{target[:16]}...")
            else:
                print(f"   ❌ NO DERIVED_FROM relationship for:")
                print(f"      pending_review/{pending_hashes[0][:16]}...")
    except Exception as e:
        print(f"   ⚠️  Error checking classification chain: {e}")
    
    print()
    
    # Check pending_review_annotation → annotated_articles
    print("2️⃣  ANNOTATION REVIEW CHAIN")
    print("-" * 70)
    
    try:
        annotation_hashes = query_folder_hashes_from_neo4j_env('pending_review_annotation/', crisis_bucket)
        print(f"   Source hashes in pending_review_annotation/: {len(annotation_hashes) if annotation_hashes else 0}")
        if annotation_hashes:
            for h in annotation_hashes[:3]:
                print(f"     - {h[:16]}...")
        
        annotated_hashes = query_folder_hashes_from_neo4j_env('annotated_articles/', crisis_bucket)
        print(f"   Target hashes in annotated_articles/: {len(annotated_hashes) if annotated_hashes else 0}")
        if annotated_hashes:
            for h in annotated_hashes[:3]:
                print(f"     - {h[:16]}...")
        
        if annotation_hashes:
            target = query_folder_hash_derived_from_source_hash_env(
                target_folder_path='annotated_articles/',
                source_folder_path='pending_review_annotation/',
                source_hash=annotation_hashes[0],
                bucket_name=crisis_bucket,
            )
            if target:
                print(f"   ✅ DERIVED_FROM relationship found!")
                print(f"      pending_review_annotation/{annotation_hashes[0][:16]}...")
                print(f"      → annotated_articles/{target[:16]}...")
            else:
                print(f"   ❌ NO DERIVED_FROM relationship for:")
                print(f"      pending_review_annotation/{annotation_hashes[0][:16]}...")
    except Exception as e:
        print(f"   ⚠️  Error checking annotation chain: {e}")
    
    print("\n" + "="*70)
    print("NEXT STEPS:")
    print("="*70)
    print("If you see ❌ NO DERIVED_FROM relationship:")
    print("  1. Run: make post-apply")
    print("  2. Or: python3 bootstrap/neo4j/restart_graph.py")
    print("  3. Then refresh the admin dashboard")
    print()

if __name__ == "__main__":
    check_hash_relationships()
