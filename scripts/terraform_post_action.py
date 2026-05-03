#!/usr/bin/env python3

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from google.cloud import storage

# Add utils to path for Neo4j utilities
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.neo4j_utils import (
    query_latest_folder_hash_from_neo4j_env,
    query_folder_hash_derived_from_env,
    write_folder_hash_to_neo4j_env,
)

TIMEOUT_SECONDS = 10
GCP_TIMEOUT_SECONDS = 120
REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_GRAPH_MANIFEST = REPO_ROOT / "bootstrap" / "neo4j" / "graph_manifest.json"
GENERATED_GRAPH_DIR = REPO_ROOT / "bootstrap" / "neo4j" / "generated"
GENERATED_GRAPH_MANIFEST = GENERATED_GRAPH_DIR / "terraform_post_action_graph.json"
BOOTSTRAP_ENV_PATH = REPO_ROOT / ".env"
NEO4J_LOADER_SCRIPT = REPO_ROOT / "bootstrap" / "neo4j" / "load_graph.py"


def print_line(text=""):
    print(text)


def sanitize_key_part(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in value)


def load_env_file(path: Path) -> dict:
    values = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key:
            values[key] = value

    return values


def env_flag(name: str, default: bool = False, env_values: dict | None = None) -> bool:
    value = os.environ.get(name)
    if value is None and env_values is not None:
        value = env_values.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def get_terraform_outputs(terraform_binary: str) -> dict:
    try:
        completed = subprocess.run(
            [terraform_binary, "output", "-json"],
            check=True,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        print(
            "terraform post-action: skipping summary because Terraform outputs "
            f"did not respond within {TIMEOUT_SECONDS} seconds.",
            file=sys.stderr,
        )
        raise SystemExit(0)
    except subprocess.CalledProcessError:
        print("terraform post-action: Terraform outputs are not available yet.", file=sys.stderr)
        print("Run this after a successful 'terraform apply' in the initialized workspace.", file=sys.stderr)
        raise SystemExit(0)

    stdout = completed.stdout.strip()
    if not stdout or stdout == "{}":
        print("terraform post-action: no Terraform outputs defined.")
        raise SystemExit(0)

    try:
        raw_outputs = json.loads(stdout)
    except json.JSONDecodeError as exc:
        print(f"terraform post-action: failed to parse Terraform outputs: {exc}", file=sys.stderr)
        raise SystemExit(1)

    return {key: value.get("value") for key, value in raw_outputs.items()}


def load_json_file(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"terraform post-action: required file not found: {path}", file=sys.stderr)
        raise SystemExit(1)
    except json.JSONDecodeError as exc:
        print(f"terraform post-action: invalid JSON in {path}: {exc}", file=sys.stderr)
        raise SystemExit(1)


def get_active_hash_type(component: dict, fallback: str = "content") -> str:
    current_use = (component.get("current_use") or "").strip().lower()
    if current_use == "local" and component.get("local_hash"):
        return "local"
    if current_use == "github" and component.get("github_hash"):
        return "github"
    if component.get("content_hash"):
        return "content"
    if component.get("local_hash"):
        return "local"
    if component.get("github_hash"):
        return "github"
    return fallback


def parse_local_hash(local_hash: str) -> dict:
    if not local_hash.startswith("LOCAL_"):
        return {"updater": "", "deployment_ref": local_hash}

    parts = local_hash.split("_", 2)
    if len(parts) == 3:
        return {"updater": parts[2], "deployment_ref": parts[1]}
    if len(parts) == 2:
        return {"updater": "", "deployment_ref": parts[1]}
    return {"updater": "", "deployment_ref": local_hash}


def parse_github_hash(github_hash: str) -> dict:
    if not github_hash.startswith("GITHUB_"):
        return {"updater": "", "deployment_ref": github_hash}

    parts = github_hash.split("_", 3)
    if len(parts) == 4:
        return {"updater": parts[3], "deployment_ref": parts[2]}
    if len(parts) == 3:
        return {"updater": "", "deployment_ref": parts[2]}
    return {"updater": "", "deployment_ref": github_hash}


def get_deployment_metadata(component: dict) -> dict:
    current_use = (component.get("current_use") or "").strip().lower()
    if current_use == "github" and component.get("github_hash"):
        parsed = parse_github_hash(component["github_hash"])
        return {
            "deployment_source": "github",
            "updater": parsed["updater"],
            "deployment_ref": parsed["deployment_ref"],
        }
    if current_use == "local" and component.get("local_hash"):
        parsed = parse_local_hash(component["local_hash"])
        return {
            "deployment_source": "local",
            "updater": parsed["updater"],
            "deployment_ref": parsed["deployment_ref"],
        }
    if component.get("github_hash"):
        parsed = parse_github_hash(component["github_hash"])
        return {
            "deployment_source": "github",
            "updater": parsed["updater"],
            "deployment_ref": parsed["deployment_ref"],
        }
    if component.get("local_hash"):
        parsed = parse_local_hash(component["local_hash"])
        return {
            "deployment_source": "local",
            "updater": parsed["updater"],
            "deployment_ref": parsed["deployment_ref"],
        }
    return {
        "deployment_source": "",
        "updater": "",
        "deployment_ref": "",
    }


def resolve_component_hash(component: dict) -> tuple[str, str]:
    content_hash = (component.get("content_hash") or "").strip()
    if content_hash:
        return "content", content_hash

    active_hash_type = get_active_hash_type(component, fallback="")
    if active_hash_type == "local":
        local_hash = (component.get("local_hash") or "").strip()
        if local_hash:
            return "local", local_hash
    if active_hash_type == "github":
        github_hash = (component.get("github_hash") or "").strip()
        if github_hash:
            return "github", github_hash

    local_hash = (component.get("local_hash") or "").strip()
    if local_hash:
        return "local", local_hash

    github_hash = (component.get("github_hash") or "").strip()
    if github_hash:
        return "github", github_hash

    return "", ""


def build_pipeline_output_hash(source_hash: str, content_hash: str) -> str:
    content_hash = (content_hash or "unknown-hash").strip()
    source_hash = (source_hash or "").strip()

    if not source_hash:
        return content_hash

    return hashlib.sha256(f"{source_hash}:{content_hash}".encode("utf-8")).hexdigest()


def build_hash_node(
    component_key: str,
    component_name: str,
    component_kind: str,
    hash_value: str,
    hash_type: str,
    deployment_metadata: dict,
) -> dict:
    node_key = f"hash:{component_kind}:{component_name}:{sanitize_key_part(hash_value)}"
    return {
        "key": node_key,
        "label": "DeploymentHash",
        "properties": {
            "name": node_key,
            "component_key": component_key,
            "component_name": component_name,
            "component_kind": component_kind,
            "hash_value": hash_value,
            "hash_type": hash_type,
            "deployment_source": deployment_metadata["deployment_source"],
            "updater": deployment_metadata["updater"],
            "deployment_ref": deployment_metadata["deployment_ref"],
        },
    }


def build_folder_hash_node(bucket_key: str, bucket_name: str, folder_path: str, hash_value: str, hash_type: str) -> dict:
    folder_name = folder_path.strip("/") or "root"
    node_key = (
        f"hash:folder:{sanitize_key_part(bucket_name)}:"
        f"{sanitize_key_part(folder_name)}:{sanitize_key_part(hash_value)}"
    )
    return {
        "key": node_key,
        "label": "FolderHash",
        "properties": {
            "name": node_key,
            "bucket_key": bucket_key,
            "bucket_name": bucket_name,
            "folder_path": folder_path,
            "folder_name": folder_name,
            "hash_value": hash_value,
            "hash_type": hash_type,
        },
    }


COMPONENT_KEY_ALIASES = {
    "service:dvb-annotator": "job:dvb-annotator-job",
    "job:dvb-annotator-job": "service:dvb-annotator",
    "service:dvb-extractor": "job:dvb-extractor-job",
    "job:dvb-extractor-job": "service:dvb-extractor",
}


def normalize_component_key(component_key: str, available_keys) -> str:
    if component_key in available_keys:
        return component_key
    alias_key = COMPONENT_KEY_ALIASES.get(component_key, "")
    if alias_key and alias_key in available_keys:
        return alias_key
    return component_key


def filter_base_manifest_by_outputs(base_manifest: dict, outputs: dict) -> dict:
    managed_prefixes = (
        "project:",
        "registry:",
        "bucket:",
        "workflow:",
        "scheduler:",
        "job:",
        "service:",
    )

    active_graph_keys_raw = outputs.get("active_graph_keys") or []
    active_graph_keys = set(active_graph_keys_raw)
    base_node_keys = {node.get("key", "") for node in base_manifest.get("nodes", [])}

    # Keep compatible aliases during job/service migration windows.
    for key in list(active_graph_keys):
        alias_key = COMPONENT_KEY_ALIASES.get(key, "")
        if alias_key and alias_key in base_node_keys:
            active_graph_keys.add(alias_key)

    use_global_pruning = len(active_graph_keys) > 0

    # Backward-compatible fallback for older output sets.
    if not use_global_pruning:
        for name in (outputs.get("jobs") or {}).keys():
            active_graph_keys.add(f"job:{name}")
        for name in (outputs.get("services") or {}).keys():
            active_graph_keys.add(f"service:{name}")

    filtered_nodes = []
    for node in base_manifest.get("nodes", []):
        key = node.get("key", "")
        if use_global_pruning:
            if key.startswith(managed_prefixes) and key not in active_graph_keys:
                continue
        else:
            if key.startswith(("job:", "service:")) and key not in active_graph_keys:
                continue
        filtered_nodes.append(node)

    filtered_node_keys = {node.get("key", "") for node in filtered_nodes}
    filtered_relationships = []
    for relationship in base_manifest.get("relationships", []):
        source = relationship.get("from", "")
        target = relationship.get("to", "")
        if source in filtered_node_keys and target in filtered_node_keys:
            filtered_relationships.append(relationship)

    return {
        "nodes": filtered_nodes,
        "relationships": filtered_relationships,
    }


def build_dynamic_hash_graph(outputs: dict, base_manifest: dict) -> dict:
    nodes = []
    relationships = []
    hash_node_keys = {}
    component_hash_values = {}
    component_hash_types = {}
    folder_hash_keys = {}
    folder_hashes_by_component = {}
    folder_hashes_by_component_path = {}
    folder_hash_value_by_key = {}
    folder_hash_producer_edges = set()
    folder_source_edges = set()

    bucket_name_by_key = {}
    for node in base_manifest.get("nodes", []):
        key = node.get("key", "")
        if key.startswith("bucket:"):
            bucket_name_by_key[key] = node.get("properties", {}).get("name", key.split(":", 1)[1])

    component_sets = [
        ("job", outputs.get("jobs") or {}),
        ("service", outputs.get("services") or {}),
    ]
    available_component_keys = {
        node.get("key", "")
        for node in base_manifest.get("nodes", [])
        if node.get("key", "").startswith(("job:", "service:"))
    }

    for component_kind, components in component_sets:
        for component_name, component in sorted(components.items()):
            if not component:
                continue

            component_key = normalize_component_key(f"{component_kind}:{component_name}", available_component_keys)
            hash_type, hash_value = resolve_component_hash(component)
            if not hash_value:
                continue

            deployment_metadata = get_deployment_metadata(component)
            node = build_hash_node(
                component_key,
                component_name,
                component_kind,
                hash_value,
                hash_type,
                deployment_metadata,
            )
            nodes.append(node)
            hash_node_keys[component_key] = node["key"]
            component_hash_values[component_key] = hash_value
            component_hash_types[component_key] = hash_type

            relationships.append(
                {
                    "from": component_key,
                    "to": node["key"],
                    "type": "HAS_HASH",
                    "properties": {
                        "hash_type": hash_type,
                        "hash_value": hash_value,
                        "deployment_source": deployment_metadata["deployment_source"],
                        "updater": deployment_metadata["updater"],
                    },
                }
            )

    writers_by_bucket = {}
    readers_by_bucket = {}
    writers_by_bucket_path = {}
    reader_inputs_by_component = {}
    component_input_lineage = {}

    # Jobs that SPAWN sub-jobs are orchestrators; exclude them from the
    # bucket-level DEPENDS_ON_DATA_FROM inference so downstream jobs are not
    # incorrectly linked to them as data sources.
    spawner_jobs = {
        r.get("from", "")
        for r in base_manifest.get("relationships", [])
        if r.get("type") == "SPAWNS"
    }

    for relationship in base_manifest.get("relationships", []):
        source = relationship.get("from", "")
        target = relationship.get("to", "")
        rel_type = relationship.get("type")
        rel_path = (relationship.get("properties", {}) or {}).get("path", "")

        if not source.startswith(("job:", "service:")) or not target.startswith("bucket:"):
            continue

        if rel_type == "WRITES_TO":
            if source not in spawner_jobs:
                writers_by_bucket.setdefault(target, set()).add(source)
            writers_by_bucket_path.setdefault((target, rel_path), set()).add(source)
        elif rel_type == "READS_FROM":
            readers_by_bucket.setdefault(target, set()).add(source)
            reader_inputs_by_component.setdefault(source, []).append((target, rel_path))

    for reader, inputs in sorted(reader_inputs_by_component.items()):
        for input_bucket, input_path in sorted(inputs):
            candidate_writers = [
                writer
                for writer in sorted(writers_by_bucket_path.get((input_bucket, input_path), set()))
                if component_hash_values.get(writer, "")
            ]
            if not candidate_writers:
                candidate_writers = [
                    writer
                    for writer in sorted(writers_by_bucket.get(input_bucket, set()))
                    if component_hash_values.get(writer, "")
                ]
            if not candidate_writers:
                continue

            upstream_source_component = candidate_writers[0]
            component_input_lineage.setdefault(
                reader,
                {
                    "source_component": upstream_source_component,
                    "source_bucket": input_bucket,
                    "source_path": input_path,
                },
            )
            break

    for relationship in base_manifest.get("relationships", []):
        source = relationship.get("from", "")
        target = relationship.get("to", "")
        rel_type = relationship.get("type")
        rel_path = (relationship.get("properties", {}) or {}).get("path", "")

        if rel_type != "WRITES_TO":
            continue
        if not source.startswith(("job:", "service:")) or not target.startswith("bucket:"):
            continue

        source_hash_key = hash_node_keys.get(source)
        source_hash_value = component_hash_values.get(source, "")
        if not source_hash_key or not source_hash_value:
            continue

        input_lineage = component_input_lineage.get(source, {})
        source_component = input_lineage.get("source_component", "")
        source_bucket = input_lineage.get("source_bucket", "")
        source_path = input_lineage.get("source_path", "")

        upstream_folder_hashes = []
        input_hash = ""
        if source_component:
            upstream_folder_hashes = sorted(
                folder_hashes_by_component_path.get((source_component, source_bucket, source_path), set())
            )
            if not upstream_folder_hashes:
                upstream_folder_hashes = sorted(folder_hashes_by_component.get(source_component, set()))
            if upstream_folder_hashes:
                input_hash = folder_hash_value_by_key.get(upstream_folder_hashes[-1], "")

        if not input_hash and source_component:
            input_hash = component_hash_values.get(source_component, "")

        folder_hash_value = build_pipeline_output_hash(input_hash, source_hash_value)
        bucket_name = bucket_name_by_key.get(target, target.split(":", 1)[1])
        folder_hash_node_id = f"{target}|{rel_path}|{folder_hash_value}"
        folder_hash_key = folder_hash_keys.get(folder_hash_node_id, "")
        if not folder_hash_key:
            folder_hash_node = build_folder_hash_node(target, bucket_name, rel_path, folder_hash_value, "pipeline")
            nodes.append(folder_hash_node)
            folder_hash_key = folder_hash_node["key"]
            folder_hash_keys[folder_hash_node_id] = folder_hash_key
            folder_hash_value_by_key[folder_hash_key] = folder_hash_value
            folder_hashes_by_component.setdefault(source, set()).add(folder_hash_key)
            folder_hashes_by_component_path.setdefault((source, target, rel_path), set()).add(folder_hash_key)
            relationships.append(
                {
                    "from": target,
                    "to": folder_hash_key,
                    "type": "HAS_HASH",
                    "properties": {
                        "hash_type": "pipeline",
                        "hash_value": folder_hash_value,
                        "path": rel_path,
                    },
                }
            )

        producer_edge_key = (folder_hash_key, source_hash_key)
        if producer_edge_key not in folder_hash_producer_edges:
            folder_hash_producer_edges.add(producer_edge_key)
            relationships.append(
                {
                    "from": folder_hash_key,
                    "to": source_hash_key,
                    "type": "PRODUCED_BY",
                    "properties": {
                        "bucket": target,
                        "path": rel_path,
                        "source_hash": input_hash,
                        "content_hash": source_hash_value,
                        "source_relation": "pipeline_output_hash",
                    },
                }
            )

        if input_hash and source_component:
            upstream_folder_hashes = sorted(
                folder_hashes_by_component_path.get((source_component, source_bucket, source_path), set())
            )
            if not upstream_folder_hashes:
                upstream_folder_hashes = sorted(folder_hashes_by_component.get(source_component, set()))
            for upstream_folder_hash_key in upstream_folder_hashes:
                if upstream_folder_hash_key == folder_hash_key:
                    continue
                lineage_edge_key = (folder_hash_key, upstream_folder_hash_key)
                if lineage_edge_key in folder_source_edges:
                    continue
                folder_source_edges.add(lineage_edge_key)
                relationships.append(
                    {
                        "from": folder_hash_key,
                        "to": upstream_folder_hash_key,
                        "type": "DEPENDS_ON_DATA_FROM",
                        "properties": {
                            "source_relation": "folder_hash_lineage",
                            "source_hash": input_hash,
                            "source_bucket": source_bucket,
                            "source_path": source_path,
                        },
                    }
                )

            # Preserve the real business flow: `crisis_articles/` is produced
            # from `pending_review/` before the annotator job runs.
            if rel_path == "crisis_articles/":
                pending_key = None
                for v in folder_hash_keys.values():
                    if ":pending_review:" in v:
                        pending_key = v
                        break
                if pending_key:
                    lineage_edge_key = (folder_hash_key, pending_key)
                    if lineage_edge_key not in folder_source_edges:
                        folder_source_edges.add(lineage_edge_key)
                        relationships.append(
                            {
                                "from": folder_hash_key,
                                "to": pending_key,
                                "type": "DEPENDS_ON_DATA_FROM",
                                "properties": {
                                    "source_relation": "folder_hash_lineage",
                                    "source_hash": folder_hash_value_by_key.get(pending_key, ""),
                                    "source_bucket": target,
                                    "source_path": "pending_review/",
                                },
                            }
                        )

            # Special-case: ensure `annotated_articles/` also depends on
            # `pending_review_annotation/` when that folder hash exists. This
            # covers the case where crisis-admin produces both stages and the
            # generator's single-source heuristic may miss the explicit link.
            if rel_path == "annotated_articles/":
                pending_key = None
                for v in folder_hash_keys.values():
                    if ":pending_review_annotation:" in v:
                        pending_key = v
                        break
                if pending_key:
                    lineage_edge_key = (folder_hash_key, pending_key)
                    if lineage_edge_key not in folder_source_edges:
                        folder_source_edges.add(lineage_edge_key)
                        relationships.append(
                            {
                                "from": folder_hash_key,
                                "to": pending_key,
                                "type": "DEPENDS_ON_DATA_FROM",
                                "properties": {
                                    "source_relation": "folder_hash_lineage",
                                    "source_hash": folder_hash_value_by_key.get(pending_key, ""),
                                    "source_bucket": target,
                                    "source_path": "pending_review_annotation/",
                                },
                            }
                        )

    folder_hash_key_by_path = {}
    for node in nodes:
        if node.get("label") != "FolderHash":
            continue
        props = node.get("properties", {})
        folder_path = props.get("folder_path", "")
        if folder_path in {"annotated_articles/", "pending_review_annotation/"}:
            folder_hash_key_by_path[folder_path] = node.get("key", "")

    annotated_folder_key = folder_hash_key_by_path.get("annotated_articles/", "")
    pending_folder_key = folder_hash_key_by_path.get("pending_review_annotation/", "")
    if annotated_folder_key and pending_folder_key:
        lineage_edge_key = (annotated_folder_key, pending_folder_key)
        if lineage_edge_key not in folder_source_edges:
            folder_source_edges.add(lineage_edge_key)
            relationships.append(
                {
                    "from": annotated_folder_key,
                    "to": pending_folder_key,
                    "type": "DEPENDS_ON_DATA_FROM",
                    "properties": {
                        "source_relation": "folder_hash_lineage",
                        "source_hash": folder_hash_value_by_key.get(pending_folder_key, ""),
                        "source_bucket": "bucket:pipeline-data",
                        "source_path": "pending_review_annotation/",
                    },
                }
            )

    all_buckets = set(writers_by_bucket) | set(readers_by_bucket)
    for bucket_key in sorted(all_buckets):
        for writer in sorted(writers_by_bucket.get(bucket_key, set())):
            for reader in sorted(readers_by_bucket.get(bucket_key, set())):
                if writer == reader:
                    continue

                relationships.append(
                    {
                        "from": reader,
                        "to": writer,
                        "type": "DEPENDS_ON_DATA_FROM",
                        "properties": {
                            "bucket": bucket_key,
                        },
                    }
                )

    return {
        "nodes": nodes,
        "relationships": relationships,
    }


def collapse_legacy_hash_graph(manifest: dict) -> dict:
    component_hash_nodes = {}
    active_hash_type_by_component = {}
    base_nodes = []
    base_relationships = []

    for node in manifest.get("nodes", []):
        if node.get("label") != "DeploymentHash":
            base_nodes.append(node)
            continue

        props = node.get("properties", {})
        component_key = props.get("component_key")
        hash_type = props.get("hash_type")
        if not component_key or not hash_type:
            continue
        component_hash_nodes.setdefault(component_key, {})[hash_type] = node

    for relationship in manifest.get("relationships", []):
        rel_type = relationship.get("type")
        if rel_type == "USES_ACTIVE_HASH":
            active_hash_type_by_component[relationship["from"]] = relationship.get("properties", {}).get("hash_type", "")
            continue
        if rel_type == "HAS_HASH":
            continue
        if rel_type == "DEPENDS_ON_DATA_FROM" and relationship.get("properties", {}).get("source_relation") == "active_hash":
            continue
        base_relationships.append(relationship)

    new_hash_nodes = []
    new_hash_relationships = []
    content_hash_key_by_component = {}

    for component_key, hashes in sorted(component_hash_nodes.items()):
        content_node = hashes.get("content")
        if not content_node:
            continue

        active_type = active_hash_type_by_component.get(component_key) or ("github" if "github" in hashes else "local" if "local" in hashes else "content")
        active_node = hashes.get(active_type)
        deployment_metadata = {"deployment_source": "", "updater": "", "deployment_ref": ""}
        if active_type == "github" and active_node:
            deployment_metadata = {
                "deployment_source": "github",
                **parse_github_hash(active_node["properties"].get("hash_value", "")),
            }
        elif active_type == "local" and active_node:
            deployment_metadata = {
                "deployment_source": "local",
                **parse_local_hash(active_node["properties"].get("hash_value", "")),
            }

        content_props = content_node.get("properties", {})
        component_name = content_props.get("component_name", component_key.split(":", 1)[1])
        component_kind = content_props.get("component_kind", component_key.split(":", 1)[0])
        hash_value = content_props.get("hash_value", "")

        new_node = build_hash_node(
            component_key,
            component_name,
            component_kind,
            hash_value,
            "content",
            deployment_metadata,
        )
        new_hash_nodes.append(new_node)
        content_hash_key_by_component[component_key] = new_node["key"]
        new_hash_relationships.append(
            {
                "from": component_key,
                "to": new_node["key"],
                "type": "HAS_HASH",
                "properties": {
                    "hash_type": "content",
                    "hash_value": hash_value,
                    "deployment_source": deployment_metadata["deployment_source"],
                    "updater": deployment_metadata["updater"],
                },
            }
        )

    writers_by_bucket = {}
    readers_by_bucket = {}
    for relationship in base_relationships:
        source = relationship.get("from", "")
        target = relationship.get("to", "")
        rel_type = relationship.get("type")
        if not source.startswith(("job:", "service:")) or not target.startswith("bucket:"):
            continue
        if rel_type == "WRITES_TO":
            writers_by_bucket.setdefault(target, set()).add(source)
        elif rel_type == "READS_FROM":
            readers_by_bucket.setdefault(target, set()).add(source)

    for bucket_key in sorted(set(writers_by_bucket) | set(readers_by_bucket)):
        for writer in sorted(writers_by_bucket.get(bucket_key, set())):
            writer_hash_key = content_hash_key_by_component.get(writer)
            if writer_hash_key:
                new_hash_relationships.append(
                    {
                        "from": writer_hash_key,
                        "to": bucket_key,
                        "type": "WRITES_TO",
                        "properties": {
                            "source_relation": "content_hash",
                        },
                    }
                )

        for reader in sorted(readers_by_bucket.get(bucket_key, set())):
            reader_hash_key = content_hash_key_by_component.get(reader)
            if reader_hash_key:
                new_hash_relationships.append(
                    {
                        "from": reader_hash_key,
                        "to": bucket_key,
                        "type": "READS_FROM",
                        "properties": {
                            "source_relation": "content_hash",
                        },
                    }
                )

        for writer in sorted(writers_by_bucket.get(bucket_key, set())):
            for reader in sorted(readers_by_bucket.get(bucket_key, set())):
                reader_hash_key = content_hash_key_by_component.get(reader)
                writer_hash_key = content_hash_key_by_component.get(writer)
                if reader_hash_key and writer_hash_key and reader_hash_key != writer_hash_key:
                    new_hash_relationships.append(
                        {
                            "from": reader_hash_key,
                            "to": writer_hash_key,
                            "type": "DEPENDS_ON_DATA_FROM",
                            "properties": {
                                "bucket": bucket_key,
                                "source_relation": "content_hash",
                            },
                        }
                    )

    return {
        "nodes": base_nodes + new_hash_nodes,
        "relationships": base_relationships + new_hash_relationships,
    }


def rebuild_graph_with_current_base(existing_manifest: dict, current_base_manifest: dict) -> dict:
    collapsed_existing = collapse_legacy_hash_graph(existing_manifest)
    current_base_keys = {node.get("key", "") for node in current_base_manifest.get("nodes", [])}

    hash_nodes = [
        node
        for node in collapsed_existing.get("nodes", [])
        if node.get("label") in {"DeploymentHash", "FolderHash"}
    ]
    hash_node_keys = {node.get("key", "") for node in hash_nodes}
    allowed_node_keys = current_base_keys | hash_node_keys

    hash_relationships = []
    for relationship in collapsed_existing.get("relationships", []):
        source = relationship.get("from", "")
        target = relationship.get("to", "")
        if (
            relationship.get("type") == "HAS_HASH"
            or source.startswith("hash:")
            or target.startswith("hash:")
        ) and source in allowed_node_keys and target in allowed_node_keys:
            hash_relationships.append(relationship)

    component_hash_keys = {}
    component_hash_values = {}
    component_hash_types = {}
    for node in hash_nodes:
        if node.get("label") != "DeploymentHash":
            continue
        props = node.get("properties", {})
        component_key = props.get("component_key")
        if component_key:
            component_hash_keys[component_key] = node["key"]
            component_hash_values[component_key] = props.get("hash_value", "")
            component_hash_types[component_key] = props.get("hash_type", "content")

    dynamic_nodes = []
    dynamic_relationships = []
    writers_by_bucket = {}
    readers_by_bucket = {}
    writers_by_bucket_path = {}
    reader_inputs_by_component = {}
    component_input_lineage = {}
    folder_hash_keys = {}
    folder_hashes_by_component = {}
    folder_hashes_by_component_path = {}
    folder_hash_value_by_key = {}
    folder_hash_producer_edges = set()
    folder_source_edges = set()

    bucket_name_by_key = {}
    for node in current_base_manifest.get("nodes", []):
        key = node.get("key", "")
        if key.startswith("bucket:"):
            bucket_name_by_key[key] = node.get("properties", {}).get("name", key.split(":", 1)[1])

    spawner_jobs = {
        r.get("from", "")
        for r in current_base_manifest.get("relationships", [])
        if r.get("type") == "SPAWNS"
    }

    for relationship in current_base_manifest.get("relationships", []):
        source = relationship.get("from", "")
        target = relationship.get("to", "")
        rel_type = relationship.get("type")
        rel_path = (relationship.get("properties", {}) or {}).get("path", "")

        if not source.startswith(("job:", "service:")) or not target.startswith("bucket:"):
            continue

        if rel_type == "WRITES_TO":
            if source not in spawner_jobs:
                writers_by_bucket.setdefault(target, set()).add(source)
            writers_by_bucket_path.setdefault((target, rel_path), set()).add(source)
        elif rel_type == "READS_FROM":
            readers_by_bucket.setdefault(target, set()).add(source)
            reader_inputs_by_component.setdefault(source, []).append((target, rel_path))

    for reader, inputs in sorted(reader_inputs_by_component.items()):
        for input_bucket, input_path in sorted(inputs):
            candidate_writers = [
                writer
                for writer in sorted(writers_by_bucket_path.get((input_bucket, input_path), set()))
                if component_hash_values.get(writer, "")
            ]
            if not candidate_writers:
                candidate_writers = [
                    writer
                    for writer in sorted(writers_by_bucket.get(input_bucket, set()))
                    if component_hash_values.get(writer, "")
                ]
            if not candidate_writers:
                continue

            upstream_source_component = candidate_writers[0]
            component_input_lineage.setdefault(
                reader,
                {
                    "source_component": upstream_source_component,
                    "source_bucket": input_bucket,
                    "source_path": input_path,
                },
            )
            break

    for relationship in current_base_manifest.get("relationships", []):
        source = relationship.get("from", "")
        target = relationship.get("to", "")
        rel_type = relationship.get("type")
        rel_path = (relationship.get("properties", {}) or {}).get("path", "")

        if rel_type != "WRITES_TO":
            continue
        if not source.startswith(("job:", "service:")) or not target.startswith("bucket:"):
            continue

        source_hash_key = component_hash_keys.get(source)
        source_hash_value = component_hash_values.get(source, "")
        if not source_hash_key or not source_hash_value:
            continue

        input_lineage = component_input_lineage.get(source, {})
        source_component = input_lineage.get("source_component", "")
        source_bucket = input_lineage.get("source_bucket", "")
        source_path = input_lineage.get("source_path", "")

        upstream_folder_hashes = []
        input_hash = ""
        if source_component:
            upstream_folder_hashes = sorted(
                folder_hashes_by_component_path.get((source_component, source_bucket, source_path), set())
            )
            if not upstream_folder_hashes:
                upstream_folder_hashes = sorted(folder_hashes_by_component.get(source_component, set()))
            if upstream_folder_hashes:
                input_hash = folder_hash_value_by_key.get(upstream_folder_hashes[-1], "")

        if not input_hash and source_component:
            input_hash = component_hash_values.get(source_component, "")

        folder_hash_value = build_pipeline_output_hash(input_hash, source_hash_value)
        bucket_name = bucket_name_by_key.get(target, target.split(":", 1)[1])
        folder_hash_node_id = f"{target}|{rel_path}|{folder_hash_value}"
        folder_hash_key = folder_hash_keys.get(folder_hash_node_id, "")
        if not folder_hash_key:
            folder_hash_node = build_folder_hash_node(target, bucket_name, rel_path, folder_hash_value, "pipeline")
            dynamic_nodes.append(folder_hash_node)
            folder_hash_key = folder_hash_node["key"]
            folder_hash_keys[folder_hash_node_id] = folder_hash_key
            folder_hash_value_by_key[folder_hash_key] = folder_hash_value
            folder_hashes_by_component.setdefault(source, set()).add(folder_hash_key)
            folder_hashes_by_component_path.setdefault((source, target, rel_path), set()).add(folder_hash_key)
            dynamic_relationships.append(
                {
                    "from": target,
                    "to": folder_hash_key,
                    "type": "HAS_HASH",
                    "properties": {
                        "hash_type": "pipeline",
                        "hash_value": folder_hash_value,
                        "path": rel_path,
                    },
                }
            )

        producer_edge_key = (folder_hash_key, source_hash_key)
        if producer_edge_key not in folder_hash_producer_edges:
            folder_hash_producer_edges.add(producer_edge_key)
            dynamic_relationships.append(
                {
                    "from": folder_hash_key,
                    "to": source_hash_key,
                    "type": "PRODUCED_BY",
                    "properties": {
                        "bucket": target,
                        "path": rel_path,
                        "source_hash": input_hash,
                        "content_hash": source_hash_value,
                        "source_relation": "pipeline_output_hash",
                    },
                }
            )

        if input_hash and source_component:
            upstream_folder_hashes = sorted(
                folder_hashes_by_component_path.get((source_component, source_bucket, source_path), set())
            )
            if not upstream_folder_hashes:
                upstream_folder_hashes = sorted(folder_hashes_by_component.get(source_component, set()))
            for upstream_folder_hash_key in upstream_folder_hashes:
                lineage_edge_key = (folder_hash_key, upstream_folder_hash_key)
                if lineage_edge_key in folder_source_edges:
                    continue
                folder_source_edges.add(lineage_edge_key)
                dynamic_relationships.append(
                    {
                        "from": folder_hash_key,
                        "to": upstream_folder_hash_key,
                        "type": "DEPENDS_ON_DATA_FROM",
                        "properties": {
                            "source_relation": "folder_hash_lineage",
                            "source_hash": input_hash,
                            "source_bucket": source_bucket,
                            "source_path": source_path,
                        },
                    }
                )

    return {
        "nodes": current_base_manifest.get("nodes", []) + hash_nodes + dynamic_nodes,
        "relationships": current_base_manifest.get("relationships", []) + hash_relationships + dynamic_relationships,
    }


def write_generated_graph(outputs: dict) -> Path:
    base_manifest = load_json_file(BASE_GRAPH_MANIFEST)
    filtered_base_manifest = filter_base_manifest_by_outputs(base_manifest, outputs)
    dynamic_graph = build_dynamic_hash_graph(outputs, filtered_base_manifest)
    merged_graph = {
        "nodes": filtered_base_manifest.get("nodes", []) + dynamic_graph["nodes"],
        "relationships": filtered_base_manifest.get("relationships", []) + dynamic_graph["relationships"],
    }

    GENERATED_GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_GRAPH_MANIFEST.write_text(json.dumps(merged_graph, indent=2), encoding="utf-8")
    return GENERATED_GRAPH_MANIFEST


def refresh_generated_graph_from_existing_file() -> Path:
    existing = load_json_file(GENERATED_GRAPH_MANIFEST)
    current_base = load_json_file(BASE_GRAPH_MANIFEST)
    rebuilt = rebuild_graph_with_current_base(existing, current_base)
    GENERATED_GRAPH_MANIFEST.write_text(json.dumps(rebuilt, indent=2), encoding="utf-8")
    return GENERATED_GRAPH_MANIFEST


def sync_graph_to_neo4j(generated_graph_path: Path) -> str:
    env_values = load_env_file(BOOTSTRAP_ENV_PATH)
    auto_load_enabled = env_flag("NEO4J_AUTO_LOAD", default=True, env_values=env_values)

    if not auto_load_enabled:
        return "disabled"

    required_keys = ["NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD"]
    missing_keys = [key for key in required_keys if not (os.environ.get(key) or env_values.get(key))]
    if missing_keys:
        return f"skipped (missing {', '.join(missing_keys)})"

    env = os.environ.copy()
    for key, value in env_values.items():
        env.setdefault(key, value)
    env["NEO4J_MANIFEST_PATH"] = str(generated_graph_path)

    try:
        completed = subprocess.run(
            [sys.executable, str(NEO4J_LOADER_SCRIPT)],
            check=True,
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            env=env,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        print("terraform post-action: timed out while syncing graph to Neo4j.", file=sys.stderr)
        raise SystemExit(1)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip()
        stdout = exc.stdout.strip()
        if stderr:
            print(stderr, file=sys.stderr)
        elif stdout:
            print(stdout, file=sys.stderr)
        else:
            print("terraform post-action: Neo4j sync failed.", file=sys.stderr)
        raise SystemExit(1)

    message = completed.stdout.strip()
    return message or "synced"


def seed_folder_created_markers(generated_graph_path: Path, outputs: dict) -> list[str]:
    """Create .FOLDER_CREATED marker files for every generated FolderHash node.

    The admin UI treats only .txt files as reviewable content, so the marker
    keeps a folder path present in GCS without changing the visible article list.

    For each folder path, this function first attempts to query Neo4j for the actual
    runtime FolderHash. If found, it uses that hash value. If not found in Neo4j,
    it falls back to the computed deployment-time hash.

    Also writes DERIVED_FROM edges in Neo4j for the static deployment-time pipeline
    stages so the first runtime run can use traversal-based queries without falling
    back to the chain-tip query.
    """
    gcs_bucket = (outputs.get("gcs_output_bucket") or "").strip()
    if not gcs_bucket:
        return []

    manifest = load_json_file(generated_graph_path)
    folder_nodes = [node for node in manifest.get("nodes", []) if node.get("label") == "FolderHash"]
    if not folder_nodes:
        return []

    # Build a folder_path → computed_hash map from the manifest for DERIVED_FROM seeding.
    computed_hash_by_folder: dict[str, str] = {}
    for node in folder_nodes:
        props = node.get("properties", {}) or {}
        fp = (props.get("folder_path") or "").strip()
        hv = (props.get("hash_value") or "").strip()
        if fp and hv:
            computed_hash_by_folder[fp] = hv

    # The ordered pipeline stages and the folder that each stage is derived from.
    # Matches the runtime DERIVED_FROM chain written by the job scripts.
    pipeline_derived_from: list[tuple[str, str]] = [
        ("dvb_cleaned/",               "dvb/"),
        ("pending_review/",            "dvb_cleaned/"),
        ("crisis_articles/",           "pending_review/"),
        ("pending_review_annotation/", "crisis_articles/"),
        ("annotated_articles/",        "pending_review_annotation/"),
        ("events/",                    "annotated_articles/"),
    ]

    for target_folder, source_folder in pipeline_derived_from:
        target_hash = computed_hash_by_folder.get(target_folder, "")
        source_hash = computed_hash_by_folder.get(source_folder, "")
        if not target_hash or not source_hash:
            continue
        # Skip if a runtime DERIVED_FROM edge already exists for this target folder.
        existing = query_folder_hash_derived_from_env(target_folder, source_folder, bucket_name=gcs_bucket)
        if existing:
            continue
        write_folder_hash_to_neo4j_env(
            folder_path=target_folder,
            hash_value=target_hash,
            bucket_name=gcs_bucket,
            source_folder_path=source_folder,
            source_folder_hash=source_hash,
        )

    client = storage.Client()
    bucket = client.bucket(gcs_bucket)
    created = []

    for node in folder_nodes:
        props = node.get("properties", {}) or {}
        folder_path = (props.get("folder_path") or "").strip()
        computed_hash = (props.get("hash_value") or "").strip()
        if not folder_path or not computed_hash:
            continue

        # Prefer the actual runtime FolderHash from Neo4j; fall back to deployment-time hash.
        hash_value = computed_hash
        try:
            neo4j_hash = query_latest_folder_hash_from_neo4j_env(folder_path, gcs_bucket)
            if neo4j_hash:
                hash_value = neo4j_hash
        except Exception:
            pass

        marker_name = f"{folder_path.rstrip('/')}/{hash_value}/.FOLDER_CREATED"
        blob = bucket.blob(marker_name)
        if blob.exists():
            continue

        blob.upload_from_string("", content_type="text/plain")
        created.append(marker_name)

    return created


def print_summary(outputs: dict, generated_graph_path: Path, neo4j_status: str) -> None:
    print_line("Terraform post-action summary")
    print_line("==============================")

    docker_repo = outputs.get("docker_repository")
    if docker_repo:
        print_line(f"Artifact Registry: {docker_repo}")
    print_line(f"Generated graph manifest: {generated_graph_path}")
    print_line(f"Neo4j sync: {neo4j_status}")

    for label, value in [
        ("Job outputs bucket", outputs.get("gcs_output_bucket")),
        ("MLflow artifacts bucket", outputs.get("mlflow_artifacts_bucket")),
    ]:
        if value:
            print_line(f"{label}: {value}")

    services = outputs.get("services") or {}
    if services:
        print_line("")
        print_line("Services")
        print_line("--------")
        for name in sorted(services):
            service = services[name] or {}
            url = service.get("public_url") or "internal/private"
            visibility = "public" if service.get("allow_public") else "restricted"
            print_line(f"- {name}: {url} ({visibility})")
            if service.get("content_hash"):
                metadata = get_deployment_metadata(service)
                print_line(f"  content_hash: {service['content_hash']}")
                if metadata["deployment_source"]:
                    print_line(f"  deployed_via: {metadata['deployment_source']}")
                if metadata["updater"]:
                    print_line(f"  updater: {metadata['updater']}")
            if service.get("console_url"):
                print_line(f"  console: {service['console_url']}")

    jobs = outputs.get("jobs") or {}
    if jobs:
        print_line("")
        print_line("Jobs")
        print_line("----")
        for name in sorted(jobs):
            job = jobs[name] or {}
            trigger = job.get("trigger_command")
            schedule = job.get("schedule") or "manual"
            print_line(f"- {name}: schedule={schedule}")
            if job.get("content_hash"):
                metadata = get_deployment_metadata(job)
                print_line(f"  content_hash: {job['content_hash']}")
                if metadata["deployment_source"]:
                    print_line(f"  deployed_via: {metadata['deployment_source']}")
                if metadata["updater"]:
                    print_line(f"  updater: {metadata['updater']}")
            if trigger:
                print_line(f"  run: {trigger}")
            if job.get("console_url"):
                print_line(f"  console: {job['console_url']}")

    print_line("")
    print_line("Next checks")
    print_line("-----------")
    for service_name, service in sorted(services.items()):
        if service and service.get("public_url"):
            print_line(f"- Open {service_name}: {service['public_url']}")

    for name in sorted(jobs):
        trigger = (jobs[name] or {}).get("trigger_command")
        if trigger:
            print_line(f"- Test {name}: {trigger} --wait")

    print_line("- Inspect full outputs: terraform output")


def sync_dashboard_events_api_url(outputs: dict) -> None:
    services = outputs.get("services") or {}
    events_api = services.get("events-api") or {}
    dashboard = services.get("crisis-dashboard") or {}

    events_api_url = (events_api.get("public_url") or "").strip()
    dashboard_url = (dashboard.get("public_url") or "").strip()
    if not events_api_url or not dashboard_url:
        return

    project_id = (os.environ.get("TF_VAR_project_id") or os.environ.get("GOOGLE_CLOUD_PROJECT") or "").strip()
    region = (os.environ.get("TF_VAR_region") or os.environ.get("GCP_REGION") or "").strip()
    if not project_id or not region:
        print_line("Dashboard API sync skipped: missing TF_VAR_project_id or TF_VAR_region.")
        return

    desired_events_url = f"{events_api_url.rstrip('/')}/events"

    current_describe = subprocess.run(
        [
            "gcloud",
            "run",
            "services",
            "describe",
            "crisis-dashboard",
            "--region",
            region,
            "--project",
            project_id,
            "--format=json",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=GCP_TIMEOUT_SECONDS,
    )
    current_service = json.loads(current_describe.stdout or "{}")
    current_env = ""
    for container in current_service.get("spec", {}).get("template", {}).get("spec", {}).get("containers", []):
        for env_var in container.get("env", []):
            if env_var.get("name") == "EVENTS_API_URL":
                current_env = (env_var.get("value") or "").strip()
                break
        if current_env:
            break

    if current_env == desired_events_url:
        print_line("Dashboard API sync: EVENTS_API_URL already points at the deployed events-api.")
        return

    subprocess.run(
        [
            "gcloud",
            "run",
            "services",
            "update",
            "crisis-dashboard",
            "--region",
            region,
            "--project",
            project_id,
            "--set-env-vars",
            f"EVENTS_API_URL={desired_events_url}",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=GCP_TIMEOUT_SECONDS,
    )
    print_line(f"Dashboard API sync: set crisis-dashboard EVENTS_API_URL to {desired_events_url}")


def main() -> int:
    terraform_binary = os.environ.get("TF", "terraform")
    try:
        outputs = get_terraform_outputs(terraform_binary)
        generated_graph_path = write_generated_graph(outputs)
        neo4j_status = sync_graph_to_neo4j(generated_graph_path)
        marker_files = seed_folder_created_markers(generated_graph_path, outputs)
        print_summary(outputs, generated_graph_path, neo4j_status)
        sync_dashboard_events_api_url(outputs)
        if marker_files:
            print_line(f"Folder markers created: {len(marker_files)}")
    except SystemExit as exc:
        if exc.code == 0 and GENERATED_GRAPH_MANIFEST.exists():
            generated_graph_path = refresh_generated_graph_from_existing_file()
            neo4j_status = sync_graph_to_neo4j(generated_graph_path)
            print_line("Terraform post-action summary")
            print_line("==============================")
            print_line("Terraform outputs were unavailable; reused existing generated graph manifest.")
            print_line(f"Generated graph manifest: {generated_graph_path}")
            print_line(f"Neo4j sync: {neo4j_status}")
            return 0
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
