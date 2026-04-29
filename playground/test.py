import os
import sys

# ✅ fix path FIRST
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from utils.neo4j_utils import query_latest_folder_hash_from_neo4j , query_latest_folder_hash_from_neo4j_env

if __name__ == "__main__":
    bucket_name = "cpe-final-project-pipeline-data"
    folder_prefix = "dvb_cleaned/"
    print("=== Testing query_latest_folder_hash_from_neo4j_env ===")
    print(f"Querying latest folder hash for prefix '{folder_prefix}' in bucket '{bucket_name}' using environment variables...")
    latest_hash = query_latest_folder_hash_from_neo4j_env(folder_prefix, bucket_name)
    print(f"Latest folder hash for '{folder_prefix}' in bucket '{bucket_name}': {latest_hash}")
    latest_hash = query_latest_folder_hash_from_neo4j(
        folder_path=folder_prefix,
        bucket_name=bucket_name,
        neo4j_uri="neo4j+s://4a6a2b6a.databases.neo4j.io",
        neo4j_user="4a6a2b6a",
        neo4j_password="5C_VdJn2ERjV_4ftwy3a0tWyLmv4cd93V871d-uxELM",
        neo4j_database="4a6a2b6a",
        )
    print(f"Latest folder hash for '{folder_prefix}' in bucket '{bucket_name}': {latest_hash}")