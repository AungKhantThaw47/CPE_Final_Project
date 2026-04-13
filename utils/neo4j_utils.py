"""Shared Neo4j utility helpers for runtime hash resolution."""

import os
import ssl
from typing import Optional

from neo4j import GraphDatabase


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

    driver_kwargs = {"auth": (neo4j_user, neo4j_password)}
    if os.environ.get("NEO4J_SKIP_SSL_VERIFY", "").strip().lower() in {"1", "true", "yes", "y", "on"}:
        driver_kwargs["ssl_context"] = ssl._create_unverified_context()

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
