"""Shared Neo4j utility helpers for runtime hash resolution."""

import os
import ssl
from typing import Optional

from neo4j import GraphDatabase


def _make_driver_kwargs(neo4j_uri: str, neo4j_user: str, neo4j_password: str) -> dict:
    driver_kwargs = {"auth": (neo4j_user, neo4j_password)}
    if os.environ.get("NEO4J_SKIP_SSL_VERIFY", "").strip().lower() in {"1", "true", "yes", "y", "on"}:
        driver_kwargs["ssl_context"] = ssl._create_unverified_context()
    return driver_kwargs


def query_latest_hash_from_neo4j(
    component_key: str,
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
    neo4j_database: str = "neo4j",
) -> Optional[str]:
    """Return latest DeploymentHash.hash_value for a component key."""
    query = """
    MATCH (c {key: $component_key})-[:HAS_HASH]->(h:DeploymentHash)
    RETURN h.hash_value AS hash_value
    LIMIT 1
    """

    driver_kwargs = _make_driver_kwargs(neo4j_uri, neo4j_user, neo4j_password)

    with GraphDatabase.driver(neo4j_uri, **driver_kwargs) as driver:
        with driver.session(database=neo4j_database) as session:
            record = session.run(query, component_key=component_key).single()
            if not record:
                return None
            value = record.get("hash_value")
            return value.strip() if isinstance(value, str) and value.strip() else None


def query_latest_hash_from_neo4j_env(component_key: str) -> Optional[str]:
    """Resolve latest hash using Neo4j connection settings from environment variables."""
    neo4j_uri = os.environ.get("NEO4J_URI", "").strip()
    neo4j_user = os.environ.get("NEO4J_USER", "").strip()
    neo4j_password = os.environ.get("NEO4J_PASSWORD", "").strip()
    neo4j_database = os.environ.get("NEO4J_DATABASE", "neo4j").strip() or "neo4j"

    if not neo4j_uri or not neo4j_user or not neo4j_password:
        return None

    try:
        return query_latest_hash_from_neo4j(
            component_key=component_key,
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password,
            neo4j_database=neo4j_database,
        )
    except Exception:
        return None


def write_output_hash_to_neo4j(
    key: str,
    hash_value: str,
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
    neo4j_database: str = "neo4j",
) -> bool:
    """Write (upsert) a runtime output hash to Neo4j under the given key.

    Creates or updates a PipelineOutputHash node so downstream jobs can look up
    the exact GCS path hash produced by an upstream step.
    """
    query = """
    MERGE (h:PipelineOutputHash {key: $key})
    SET h.hash_value = $hash_value, h.updated_at = datetime()
    """

    driver_kwargs = _make_driver_kwargs(neo4j_uri, neo4j_user, neo4j_password)

    with GraphDatabase.driver(neo4j_uri, **driver_kwargs) as driver:
        with driver.session(database=neo4j_database) as session:
            session.run(query, key=key, hash_value=hash_value)
    return True


def write_output_hash_to_neo4j_env(key: str, hash_value: str) -> bool:
    """Write output hash using Neo4j connection settings from environment variables.

    Returns True on success, False if Neo4j is not configured or write fails.
    """
    neo4j_uri = os.environ.get("NEO4J_URI", "").strip()
    neo4j_user = os.environ.get("NEO4J_USER", "").strip()
    neo4j_password = os.environ.get("NEO4J_PASSWORD", "").strip()
    neo4j_database = os.environ.get("NEO4J_DATABASE", "neo4j").strip() or "neo4j"

    if not neo4j_uri or not neo4j_user or not neo4j_password:
        return False

    try:
        return write_output_hash_to_neo4j(
            key=key,
            hash_value=hash_value,
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password,
            neo4j_database=neo4j_database,
        )
    except Exception:
        return False


def query_output_hash_from_neo4j(
    key: str,
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
    neo4j_database: str = "neo4j",
) -> Optional[str]:
    """Return the runtime output hash stored under the given key."""
    query = """
    MATCH (h:PipelineOutputHash {key: $key})
    RETURN h.hash_value AS hash_value
    """

    driver_kwargs = _make_driver_kwargs(neo4j_uri, neo4j_user, neo4j_password)

    with GraphDatabase.driver(neo4j_uri, **driver_kwargs) as driver:
        with driver.session(database=neo4j_database) as session:
            record = session.run(query, key=key).single()
            if not record:
                return None
            value = record.get("hash_value")
            return value.strip() if isinstance(value, str) and value.strip() else None


def query_output_hash_from_neo4j_env(key: str) -> Optional[str]:
    """Query runtime output hash using Neo4j connection settings from environment variables."""
    neo4j_uri = os.environ.get("NEO4J_URI", "").strip()
    neo4j_user = os.environ.get("NEO4J_USER", "").strip()
    neo4j_password = os.environ.get("NEO4J_PASSWORD", "").strip()
    neo4j_database = os.environ.get("NEO4J_DATABASE", "neo4j").strip() or "neo4j"

    if not neo4j_uri or not neo4j_user or not neo4j_password:
        return None

    try:
        return query_output_hash_from_neo4j(
            key=key,
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password,
            neo4j_database=neo4j_database,
        )
    except Exception:
        return None


def query_latest_folder_hash_from_neo4j(
    folder_path: str,
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
    neo4j_database: str = "neo4j",
    bucket_name: str = "",
) -> Optional[str]:
    """Return latest FolderHash.hash_value for a folder path and optional bucket.

    This resolves through StorageBucket-[:HAS_HASH]->FolderHash which points to
    the current folder hash in the system graph.
    """
    query = """
    MATCH (bucket:StorageBucket)-[:HAS_HASH]->(h:FolderHash {folder_path: $folder_path})
    WHERE $bucket_name = "" OR h.bucket_name = $bucket_name OR bucket.name = $bucket_name
    RETURN h.hash_value AS hash_value
    LIMIT 1
    """

    driver_kwargs = _make_driver_kwargs(neo4j_uri, neo4j_user, neo4j_password)

    with GraphDatabase.driver(neo4j_uri, **driver_kwargs) as driver:
        with driver.session(database=neo4j_database) as session:
            record = session.run(
                query,
                folder_path=folder_path,
                bucket_name=(bucket_name or "").strip(),
            ).single()
            if not record:
                return None
            value = record.get("hash_value")
            return value.strip() if isinstance(value, str) and value.strip() else None


def query_latest_folder_hash_from_neo4j_env(folder_path: str, bucket_name: str = "") -> Optional[str]:
    """Resolve latest FolderHash using Neo4j connection settings from environment variables."""
    neo4j_uri = os.environ.get("NEO4J_URI", "").strip()
    neo4j_user = os.environ.get("NEO4J_USER", "").strip()
    neo4j_password = os.environ.get("NEO4J_PASSWORD", "").strip()
    neo4j_database = os.environ.get("NEO4J_DATABASE", "neo4j").strip() or "neo4j"

    if not neo4j_uri or not neo4j_user or not neo4j_password:
        return None

    try:
        return query_latest_folder_hash_from_neo4j(
            folder_path=folder_path,
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password,
            neo4j_database=neo4j_database,
            bucket_name=bucket_name,
        )
    except Exception:
        return None
