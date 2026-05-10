#!/usr/bin/env python3
"""
Analyze Neo4j graph for latest hashes, N-to-N and 1-to-1 relationships.
"""
import os
import json
import ssl
import urllib.request
import urllib.parse
from typing import Any, Dict, List

def get_neo4j_credentials() -> Dict[str, str]:
    """Get Neo4j credentials from environment."""
    return {
        "uri": os.getenv("NEO4J_URI", "neo4j+s://4a6a2b6a.databases.neo4j.io"),
        "user": os.getenv("NEO4J_USER", "4a6a2b6a"),
        "password": os.getenv("NEO4J_PASSWORD", ""),
        "database": os.getenv("NEO4J_DATABASE", "4a6a2b6a"),
    }

def query_neo4j_http(query: str, creds: Dict[str, str]) -> List[List[Any]]:
    """Execute Cypher query against Neo4j using HTTP Query API v2."""
    uri = creds["uri"]
    user = creds["user"]
    password = creds["password"]
    database = creds["database"]
    
    # Extract hostname from neo4j+s://hostname format
    hostname = uri.replace("neo4j+s://", "").replace("neo4j://", "").split("/")[0]
    api_url = f"https://{hostname}/db/{urllib.parse.quote(database)}/query/v2"
    
    # Create unverified SSL context
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    auth_str = f"{user}:{password}"
    auth_b64 = __import__('base64').b64encode(auth_str.encode()).decode()
    
    payload = json.dumps({"statement": query, "parameters": {}}).encode()
    
    request = urllib.request.Request(
        api_url,
        data=payload,
        headers={
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    
    try:
        with urllib.request.urlopen(request, context=ssl_context, timeout=30) as response:
            result = json.loads(response.read().decode())
            data = result.get("data", {})
            return data.get("values", [])
    except Exception as e:
        print(f"❌ Query failed: {e}")
        raise

def analyze_latest_hashes(creds: Dict[str, str]) -> None:
    """Query latest hash for each folder_path."""
    print("\n" + "="*80)
    print("📊 LATEST HASHES PER FOLDER (Chain Tips)")
    print("="*80)
    
    # Simple query: just get all FolderHash nodes
    query = "MATCH (fh:FolderHash) RETURN fh.folder_path, fh.system_hash, fh.updated_at ORDER BY fh.folder_path, fh.updated_at DESC"
    
    results = query_neo4j_http(query, creds)
    
    if not results:
        print("No FolderHash nodes found")
        return
    
    # Group by folder_path and get latest per folder
    by_folder = {}
    for row in results:
        folder = row[0]
        hash_val = row[1]
        timestamp = row[2]
        
        if folder not in by_folder:
            by_folder[folder] = {
                'latest_hash': hash_val,
                'latest_timestamp': timestamp,
                'versions': set()
            }
        by_folder[folder]['versions'].add(hash_val)
    
    print(f"\n{'Folder Path':<40} {'Latest Hash':<18} {'Versions':<10} {'Updated':<25}")
    print("-" * 100)
    
    for folder in sorted(by_folder.keys()):
        info = by_folder[folder]
        hash_short = info['latest_hash'][:16] if info['latest_hash'] else "N/A"
        versions = len(info['versions'])
        timestamp = info['latest_timestamp']
        print(f"{folder:<40} {hash_short:<18} {versions:<10} {timestamp:<25}")
    
    print(f"\nTotal folders: {len(by_folder)}")

def analyze_derived_from_cardinality(creds: Dict[str, str]) -> None:
    """Analyze DERIVED_FROM relationships for cardinality."""
    print("\n" + "="*80)
    print("🔗 DERIVED_FROM RELATIONSHIP CARDINALITY")
    print("="*80)
    
    # Query all DERIVED_FROM edges
    query = "MATCH (source:FolderHash)-[df:DERIVED_FROM]->(target:FolderHash) RETURN source.folder_path, target.folder_path, source.system_hash, target.system_hash"
    
    results = query_neo4j_http(query, creds)
    
    if not results:
        print("\n⚠️  No DERIVED_FROM relationships found")
        return
    
    # Analyze cardinality
    edge_map = {}  # (source_folder, target_folder) -> {source_hashes, target_hashes, edges}
    
    for row in results:
        src_folder = row[0]
        tgt_folder = row[1]
        src_hash = row[2]
        tgt_hash = row[3]
        
        key = (src_folder, tgt_folder)
        if key not in edge_map:
            edge_map[key] = {
                'source_hashes': set(),
                'target_hashes': set(),
                'edges': 0
            }
        edge_map[key]['source_hashes'].add(src_hash)
        edge_map[key]['target_hashes'].add(tgt_hash)
        edge_map[key]['edges'] += 1
    
    print(f"\n{'Source':<25} {'Target':<25} {'Src Hashes':<12} {'Tgt Hashes':<12} {'Edges':<8} {'Type':<10}")
    print("-" * 100)
    
    one_to_one = 0
    n_to_n = 0
    
    for (src_folder, tgt_folder) in sorted(edge_map.keys()):
        info = edge_map[(src_folder, tgt_folder)]
        src_count = len(info['source_hashes'])
        tgt_count = len(info['target_hashes'])
        edge_count = info['edges']
        
        if src_count == 1 and tgt_count == 1:
            rel_type = '1-to-1'
            one_to_one += 1
        else:
            rel_type = 'N-to-N'
            n_to_n += 1
        
        print(f"{src_folder:<25} {tgt_folder:<25} {src_count:<12} {tgt_count:<12} {edge_count:<8} {rel_type:<10}")
    
    print(f"\nRelationship Summary:")
    print(f"  1-to-1 pairs: {one_to_one}")
    print(f"  N-to-N pairs: {n_to_n}")
    print(f"  Total edges: {len(results)}")

def analyze_one_to_one_mappings(creds: Dict[str, str]) -> None:
    """Get detailed 1-to-1 mappings."""
    print("\n" + "="*80)
    print("1️⃣➡️1️⃣  ONE-TO-ONE MAPPINGS DETAIL")
    print("="*80)
    
    # Query all DERIVED_FROM edges
    query = "MATCH (source:FolderHash)-[df:DERIVED_FROM]->(target:FolderHash) RETURN source.folder_path, target.folder_path, source.system_hash, target.system_hash"
    
    results = query_neo4j_http(query, creds)
    
    if not results:
        print("\n⚠️  No DERIVED_FROM relationships found")
        return
    
    # Find 1-to-1 mappings
    edge_map = {}
    for row in results:
        src_folder = row[0]
        tgt_folder = row[1]
        src_hash = row[2]
        tgt_hash = row[3]
        
        key = (src_folder, tgt_folder)
        if key not in edge_map:
            edge_map[key] = {'source_hashes': set(), 'target_hashes': set(), 'edges': []}
        edge_map[key]['source_hashes'].add(src_hash)
        edge_map[key]['target_hashes'].add(tgt_hash)
        edge_map[key]['edges'].append((src_hash, tgt_hash))
    
    print(f"\n{'Source Folder':<25} {'Target Folder':<25} {'1-to-1 Count':<15}")
    print("-" * 65)
    
    total_one_to_one = 0
    for (src_folder, tgt_folder) in sorted(edge_map.keys()):
        info = edge_map[(src_folder, tgt_folder)]
        if len(info['source_hashes']) == 1 and len(info['target_hashes']) == 1:
            print(f"{src_folder:<25} {tgt_folder:<25} {len(info['edges']):<15}")
            total_one_to_one += 1
    
    print(f"\nTotal 1-to-1 folder pairs: {total_one_to_one}")

def analyze_n_to_n_mappings(creds: Dict[str, str]) -> None:
    """Get N-to-N mapping statistics."""
    print("\n" + "="*80)
    print("🔄 N-TO-N MAPPINGS DETAIL")
    print("="*80)
    
    # Query all DERIVED_FROM edges
    query = "MATCH (source:FolderHash)-[df:DERIVED_FROM]->(target:FolderHash) RETURN source.folder_path, target.folder_path, source.system_hash, target.system_hash"
    
    results = query_neo4j_http(query, creds)
    
    if not results:
        print("\n⚠️  No DERIVED_FROM relationships found")
        return
    
    # Find N-to-N mappings
    edge_map = {}
    for row in results:
        src_folder = row[0]
        tgt_folder = row[1]
        src_hash = row[2]
        tgt_hash = row[3]
        
        key = (src_folder, tgt_folder)
        if key not in edge_map:
            edge_map[key] = {'source_hashes': set(), 'target_hashes': set(), 'edges': []}
        edge_map[key]['source_hashes'].add(src_hash)
        edge_map[key]['target_hashes'].add(tgt_hash)
        edge_map[key]['edges'].append((src_hash, tgt_hash))
    
    print(f"\n{'Source':<25} {'Target':<25} {'Src Count':<12} {'Tgt Count':<12} {'Edges':<12}")
    print("-" * 100)
    
    total_n_to_n_pairs = 0
    for (src_folder, tgt_folder) in sorted(edge_map.keys()):
        info = edge_map[(src_folder, tgt_folder)]
        src_count = len(info['source_hashes'])
        tgt_count = len(info['target_hashes'])
        
        if src_count > 1 or tgt_count > 1:
            print(f"{src_folder:<25} {tgt_folder:<25} {src_count:<12} {tgt_count:<12} {len(info['edges']):<12}")
            total_n_to_n_pairs += 1
    
    if total_n_to_n_pairs == 0:
        print("  (none found)")
    else:
        print(f"\nTotal N-to-N folder pairs: {total_n_to_n_pairs}")

def analyze_graph_topology(creds: Dict[str, str]) -> None:
    """Analyze overall graph topology."""
    print("\n" + "="*80)
    print("📈 GRAPH TOPOLOGY SUMMARY")
    print("="*80)
    
    # Total nodes
    query_nodes = "MATCH (fh:FolderHash) RETURN COUNT(fh)"
    nodes_result = query_neo4j_http(query_nodes, creds)
    total_nodes = nodes_result[0][0] if nodes_result and nodes_result[0] else 0
    
    # Total DERIVED_FROM edges
    query_edges = "MATCH ()-[df:DERIVED_FROM]->() RETURN COUNT(df)"
    edges_result = query_neo4j_http(query_edges, creds)
    total_edges = edges_result[0][0] if edges_result and edges_result[0] else 0
    
    # DEPENDS_ON_DATA_FROM edges
    query_depends = "MATCH ()-[d:DEPENDS_ON_DATA_FROM]->() RETURN COUNT(d)"
    depends_result = query_neo4j_http(query_depends, creds)
    total_depends = depends_result[0][0] if depends_result and depends_result[0] else 0
    
    # PREVIOUS_FOLDER_HASH edges
    query_previous = "MATCH ()-[p:PREVIOUS_FOLDER_HASH]->() RETURN COUNT(p)"
    previous_result = query_neo4j_http(query_previous, creds)
    total_previous = previous_result[0][0] if previous_result and previous_result[0] else 0
    
    print(f"\nTotal FolderHash nodes: {total_nodes}")
    print(f"Total DERIVED_FROM edges: {total_edges}")
    print(f"Total DEPENDS_ON_DATA_FROM edges: {total_depends}")
    print(f"Total PREVIOUS_FOLDER_HASH edges: {total_previous}")
    
    # Get unique folders
    query_folders = "MATCH (fh:FolderHash) RETURN COUNT(DISTINCT fh.folder_path)"
    folders_result = query_neo4j_http(query_folders, creds)
    unique_folders = folders_result[0][0] if folders_result and folders_result[0] else 0
    
    print(f"Unique folder paths: {unique_folders}")

def main():
    """Run all analyses."""
    print("🔍 Neo4j Graph Analysis")
    print("=" * 80)
    
    creds = get_neo4j_credentials()
    
    if not creds["password"]:
        print("❌ NEO4J_PASSWORD not set in environment")
        return
    
    try:
        print(f"✓ Connecting to Neo4j: {creds['uri']}")
        print(f"  Database: {creds['database']}")
        print(f"  User: {creds['user']}")
        
        analyze_latest_hashes(creds)
        analyze_derived_from_cardinality(creds)
        analyze_one_to_one_mappings(creds)
        analyze_n_to_n_mappings(creds)
        analyze_graph_topology(creds)
        
        print("\n" + "="*80)
        print("✅ Analysis complete")
        print("="*80)
        
    except Exception as e:
        print(f"\n❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
