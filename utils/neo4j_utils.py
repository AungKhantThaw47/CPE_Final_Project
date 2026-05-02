"""Shared Neo4j utility helpers for runtime hash resolution."""

import os
import ssl
from pathlib import Path
from typing import Optional

from google.cloud import storage
from neo4j import GraphDatabase


_DOTENV_LOADED = False


def _load_env_file_if_present() -> None:
    """Load repo-local .env values for local Neo4j queries without overriding env."""
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    _DOTENV_LOADED = True

    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parents[1] / ".env",
    ]

    env_path = next((path for path in candidates if path.exists()), None)
    if not env_path:
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


def _make_driver_kwargs(neo4j_uri: str, neo4j_user: str, neo4j_password: str) -> dict:
    driver_kwargs = {"auth": (neo4j_user, neo4j_password)}
    skip_ssl_verify = os.environ.get("NEO4J_SKIP_SSL_VERIFY", "").strip().lower() in {"1", "true", "yes", "y", "on"}
    if skip_ssl_verify and neo4j_uri.startswith(("bolt://", "neo4j://")):
        driver_kwargs["ssl_context"] = ssl._create_unverified_context()
    return driver_kwargs


def query_latest_hash_from_neo4j(
    component_key: str,
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
    neo4j_database: str = "neo4j",
) -> Optional[str]:
    """Return latest DeploymentHash.hash_value for a component key.

    Uses relation-based traversal: finds the chain tip by checking that no other
    DeploymentHash points to it via PREVIOUS_HASH.
    """
    query = """
    MATCH (c {key: $component_key})-[:HAS_HASH]->(h:DeploymentHash)
    OPTIONAL MATCH (newer:DeploymentHash)-[:PREVIOUS_HASH]->(h)
    WITH h, newer
    WHERE newer IS NULL
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
    _load_env_file_if_present()
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
    _load_env_file_if_present()
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
    _load_env_file_if_present()
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
    """Return latest FolderHash.hash_value for a folder path.

    Returns the current chain tip for the requested folder path.
    When a bucket name is provided, only returns hashes whose GCS folder actually has blobs.
    This avoids post-apply deployment seeds from hiding the last real output.
    """
    query = """
    MATCH (fh:FolderHash {folder_path: $folder_path})
    WHERE NOT EXISTS {
        MATCH (:FolderHash)-[:PREVIOUS_FOLDER_HASH]->(fh)
    }
    RETURN fh.hash_value AS hash_value
    ORDER BY fh.updated_at DESC
    LIMIT 1
    """

    driver_kwargs = _make_driver_kwargs(neo4j_uri, neo4j_user, neo4j_password)

    with GraphDatabase.driver(neo4j_uri, **driver_kwargs) as driver:
        with driver.session(database=neo4j_database) as session:
            records = session.run(
                query,
                folder_path=folder_path,
            ).data()

            if not records:
                return None

            if bucket_name:
                client = storage.Client()
                for record in records:
                    value = record.get("hash_value")
                    if not isinstance(value, str) or not value.strip():
                        continue

                    prefix = f"{folder_path.rstrip('/')}/{value.strip()}/"
                    try:
                        blob = next(client.list_blobs(bucket_name, prefix=prefix, max_results=1), None)
                    except Exception:
                        blob = None

                    if blob is not None:
                        return value.strip()

                value = records[0].get("hash_value")
                return value.strip() if isinstance(value, str) and value.strip() else None

            value = records[0].get("hash_value")
            return value.strip() if isinstance(value, str) and value.strip() else None


def query_latest_folder_hash_from_neo4j_env(folder_path: str, bucket_name: str = "") -> Optional[str]:
    """Resolve latest FolderHash using Neo4j connection settings from environment variables."""
    _load_env_file_if_present()
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


def write_folder_hash_to_neo4j(
    folder_path: str,
    hash_value: str,
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
    neo4j_database: str = "neo4j",
    bucket_name: str = "",
    producer_component_key: str = "",
    source_folder_path: str = "",
    source_folder_hash: str = "",
) -> bool:
    """Create/update a FolderHash node at runtime; link to previous hash if it exists.

    When source_folder_path and source_folder_hash are provided, also writes a
    DERIVED_FROM edge from the new FolderHash to the source FolderHash so that
    downstream jobs can traverse version chains across folder boundaries.
    """
    query = """
    OPTIONAL MATCH (latest:FolderHash {folder_path: $folder_path})
    WHERE NOT EXISTS {
        MATCH (:FolderHash)-[:PREVIOUS_FOLDER_HASH]->(latest)
    }

    OPTIONAL MATCH (bucket:StorageBucket)
    WHERE bucket.key IN $bucket_keys OR bucket.name IN $bucket_names OR bucket.bucket_name IN $bucket_names

    OPTIONAL MATCH (producer:DeploymentHash {component_key: $producer_component_key})

    // Create the new FolderHash node
    MERGE (new_hash:FolderHash {folder_path: $folder_path, hash_value: $hash_value})
    SET new_hash.updated_at = datetime(),
        new_hash.hash_type = coalesce(new_hash.hash_type, "runtime"),
        new_hash.bucket_name = coalesce(new_hash.bucket_name, $bucket_name)

    // Link new hash to previous hash if one exists
    WITH new_hash, latest, bucket, producer
    FOREACH (_ IN CASE WHEN latest IS NOT NULL AND latest.hash_value <> new_hash.hash_value THEN [1] ELSE [] END |
        CREATE (new_hash)-[:PREVIOUS_FOLDER_HASH]->(latest)
    )

    FOREACH (_ IN CASE WHEN bucket IS NOT NULL THEN [1] ELSE [] END |
        MERGE (bucket)-[:HAS_HASH]->(new_hash)
    )

    FOREACH (_ IN CASE WHEN producer IS NOT NULL THEN [1] ELSE [] END |
        MERGE (new_hash)-[:PRODUCED_BY]->(producer)
    )

    // Write cross-folder DERIVED_FROM edge for version-chain traversal
    FOREACH (_ IN CASE WHEN $source_folder_path <> '' AND $source_folder_hash <> '' THEN [1] ELSE [] END |
        MERGE (src:FolderHash {folder_path: $source_folder_path, hash_value: $source_folder_hash})
        MERGE (new_hash)-[:DERIVED_FROM]->(src)
    )
    """

    bucket_candidates = {bucket_name.strip()}
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
    if project_id and bucket_name.startswith(f"{project_id}-"):
        bucket_candidates.add(bucket_name[len(project_id) + 1 :].strip())
    bucket_candidates.discard("")
    bucket_keys = {f"bucket:{name}" for name in bucket_candidates}

    driver_kwargs = _make_driver_kwargs(neo4j_uri, neo4j_user, neo4j_password)

    try:
        with GraphDatabase.driver(neo4j_uri, **driver_kwargs) as driver:
            with driver.session(database=neo4j_database) as session:
                session.run(
                    query,
                    folder_path=folder_path,
                    hash_value=hash_value,
                    bucket_name=bucket_name,
                    bucket_names=sorted(bucket_candidates),
                    bucket_keys=sorted(bucket_keys),
                    producer_component_key=producer_component_key,
                    source_folder_path=source_folder_path or "",
                    source_folder_hash=source_folder_hash or "",
                )
        return True
    except Exception:
        return False


def write_folder_hash_to_neo4j_env(
    folder_path: str,
    hash_value: str,
    bucket_name: str = "",
    producer_component_key: str = "",
    source_folder_path: str = "",
    source_folder_hash: str = "",
) -> bool:
    """Write FolderHash using Neo4j connection settings from environment variables."""
    _load_env_file_if_present()
    neo4j_uri = os.environ.get("NEO4J_URI", "").strip()
    neo4j_user = os.environ.get("NEO4J_USER", "").strip()
    neo4j_password = os.environ.get("NEO4J_PASSWORD", "").strip()
    neo4j_database = os.environ.get("NEO4J_DATABASE", "neo4j").strip() or "neo4j"

    if not neo4j_uri or not neo4j_user or not neo4j_password:
        return False

    try:
        return write_folder_hash_to_neo4j(
            folder_path=folder_path,
            hash_value=hash_value,
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password,
            neo4j_database=neo4j_database,
            bucket_name=bucket_name,
            producer_component_key=producer_component_key,
            source_folder_path=source_folder_path,
            source_folder_hash=source_folder_hash,
        )
    except Exception:
        return False


def create_main_pipeline_linkage(
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
    neo4j_database: str = "neo4j",
) -> tuple[bool, str]:
    """Create DEPENDS_ON_DATA_FROM relationships for the main pipeline in correct order.

    Pipeline order: dvb → dvb_cleaned → pending_review → crisis_articles → pending_review_annotation → annotated_articles → events

    Returns (success: bool, message: str) where message describes the result.
    """
    pipeline_stages = [
        "dvb/",
        "dvb_cleaned/",
        "pending_review/",
        "crisis_articles/",
        "pending_review_annotation/",
        "annotated_articles/",
        "events/",
    ]

    driver_kwargs = _make_driver_kwargs(neo4j_uri, neo4j_user, neo4j_password)

    try:
        with GraphDatabase.driver(neo4j_uri, **driver_kwargs) as driver:
            with driver.session(database=neo4j_database) as session:
                # First, fetch latest FolderHash for each stage (chain tip only)
                stage_hashes = {}
                for stage in pipeline_stages:
                    query = """
                    MATCH (fh:FolderHash {folder_path: $folder_path})
                    WHERE NOT EXISTS {
                        MATCH (:FolderHash)-[:PREVIOUS_FOLDER_HASH]->(fh)
                    }
                    RETURN fh
                    ORDER BY fh.updated_at DESC
                    LIMIT 1
                    """
                    record = session.run(query, folder_path=stage).single()
                    if record:
                        stage_hashes[stage] = record["fh"]
                    else:
                        stage_hashes[stage] = None

                missing_stages = [s for s, h in stage_hashes.items() if h is None]
                if missing_stages:
                    return False, f"Missing FolderHash nodes for stages: {', '.join(missing_stages)}"

                # Create DEPENDS_ON_DATA_FROM links between consecutive stages
                edges_created = 0
                for i in range(len(pipeline_stages) - 1):
                    source_stage = pipeline_stages[i]
                    target_stage = pipeline_stages[i + 1]
                    source_node = stage_hashes[source_stage]
                    target_node = stage_hashes[target_stage]

                    if not source_node or not target_node:
                        continue

                    # Check if edge already exists
                    check_query = """
                    MATCH (target:FolderHash {folder_path: $target_path})
                    MATCH (source:FolderHash {folder_path: $source_path})
                    OPTIONAL MATCH (target)-[:DEPENDS_ON_DATA_FROM]->(source)
                    RETURN COUNT(*) AS edge_count
                    """
                    edge_count = session.run(
                        check_query,
                        target_path=target_stage,
                        source_path=source_stage,
                    ).single()["edge_count"]

                    if edge_count > 0:
                        continue  # Edge already exists

                    # Create the edge
                    create_edge_query = """
                    MATCH (target:FolderHash {folder_path: $target_path})
                    MATCH (source:FolderHash {folder_path: $source_path})
                    WHERE NOT EXISTS {
                        MATCH (target)-[:DEPENDS_ON_DATA_FROM]->(source)
                    }
                    CREATE (target)-[:DEPENDS_ON_DATA_FROM {
                        source_relation: "main_pipeline_linkage",
                        created_at: datetime()
                    }]->(source)
                    """
                    session.run(
                        create_edge_query,
                        target_path=target_stage,
                        source_path=source_stage,
                    )
                    edges_created += 1

                return True, f"Successfully linked {edges_created} main pipeline stages: {' → '.join(pipeline_stages)}"

    except Exception as exc:
        return False, f"Failed to create main pipeline linkage: {exc}"


def query_folder_hash_derived_from(
    target_folder_path: str,
    source_folder_path: str,
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
    neo4j_database: str = "neo4j",
    bucket_name: str = "",
) -> Optional[str]:
    """Return the FolderHash for target_folder that was DERIVED_FROM the latest source_folder hash.

    Traverses the DERIVED_FROM graph: finds the chain tip of source_folder, then returns
    the target_folder hash that has a DERIVED_FROM edge pointing to that source tip.
    This enables version-chain-aware queries — each job finds its input hash from the
    same version chain as the upstream job that produced the data it should process.
    """
    query = """
    MATCH (source:FolderHash {folder_path: $source_folder_path})
    WHERE NOT EXISTS {
        MATCH (:FolderHash)-[:PREVIOUS_FOLDER_HASH]->(source)
    }
    MATCH (target:FolderHash {folder_path: $target_folder_path})-[:DERIVED_FROM]->(source)
    RETURN target.hash_value AS hash_value, target.updated_at AS updated_at
    ORDER BY target.updated_at DESC
    LIMIT 1
    """

    driver_kwargs = _make_driver_kwargs(neo4j_uri, neo4j_user, neo4j_password)

    with GraphDatabase.driver(neo4j_uri, **driver_kwargs) as driver:
        with driver.session(database=neo4j_database) as session:
            records = session.run(
                query,
                source_folder_path=source_folder_path,
                target_folder_path=target_folder_path,
            ).data()

            if not records:
                return None

            if bucket_name:
                client = storage.Client()
                for record in records:
                    value = record.get("hash_value")
                    if not isinstance(value, str) or not value.strip():
                        continue
                    prefix = f"{target_folder_path.rstrip('/')}/{value.strip()}/"
                    try:
                        blob = next(client.list_blobs(bucket_name, prefix=prefix, max_results=1), None)
                    except Exception:
                        blob = None
                    if blob is not None:
                        return value.strip()
                value = records[0].get("hash_value")
                return value.strip() if isinstance(value, str) and value.strip() else None

            value = records[0].get("hash_value")
            return value.strip() if isinstance(value, str) and value.strip() else None


def query_folder_hash_derived_from_env(
    target_folder_path: str,
    source_folder_path: str,
    bucket_name: str = "",
) -> Optional[str]:
    """Return target FolderHash derived from the latest source FolderHash, using env-based Neo4j config."""
    _load_env_file_if_present()
    neo4j_uri = os.environ.get("NEO4J_URI", "").strip()
    neo4j_user = os.environ.get("NEO4J_USER", "").strip()
    neo4j_password = os.environ.get("NEO4J_PASSWORD", "").strip()
    neo4j_database = os.environ.get("NEO4J_DATABASE", "neo4j").strip() or "neo4j"

    if not neo4j_uri or not neo4j_user or not neo4j_password:
        return None

    try:
        return query_folder_hash_derived_from(
            target_folder_path=target_folder_path,
            source_folder_path=source_folder_path,
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password,
            neo4j_database=neo4j_database,
            bucket_name=bucket_name,
        )
    except Exception:
        return None


def create_main_pipeline_linkage_env() -> tuple[bool, str]:
    """Create main pipeline linkage using Neo4j connection settings from environment variables.

    Returns (success: bool, message: str).
    """
    _load_env_file_if_present()
    neo4j_uri = os.environ.get("NEO4J_URI", "").strip()
    neo4j_user = os.environ.get("NEO4J_USER", "").strip()
    neo4j_password = os.environ.get("NEO4J_PASSWORD", "").strip()
    neo4j_database = os.environ.get("NEO4J_DATABASE", "neo4j").strip() or "neo4j"

    if not neo4j_uri or not neo4j_user or not neo4j_password:
        return False, "Neo4j credentials not configured in environment"

    return create_main_pipeline_linkage(
        neo4j_uri=neo4j_uri,
        neo4j_user=neo4j_user,
        neo4j_password=neo4j_password,
        neo4j_database=neo4j_database,
    )
