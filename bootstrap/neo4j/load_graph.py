#!/usr/bin/env python3

import base64
import json
import os
from pathlib import Path
import sys
from urllib import error, parse, request


DEFAULT_MANIFEST = Path(__file__).with_name("graph_manifest.json")
DEFAULT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    print(f"Missing required environment variable: {name}", file=sys.stderr)
    raise SystemExit(1)


def env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_config() -> dict:
    env_path = Path(os.environ.get("BOOTSTRAP_ENV_FILE", DEFAULT_ENV_PATH)).resolve()
    load_env_file(env_path)

    manifest_path = Path(os.environ.get("NEO4J_MANIFEST_PATH", str(DEFAULT_MANIFEST))).resolve()
    return {
        "uri": require_env("NEO4J_URI"),
        "user": require_env("NEO4J_USER"),
        "password": require_env("NEO4J_PASSWORD"),
        "database": os.environ.get("NEO4J_DATABASE", "neo4j").strip() or "neo4j",
        "manifest_path": manifest_path,
        "clean": env_flag("NEO4J_CLEAN", default=False),
    }


def load_manifest(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"Manifest not found: {path}", file=sys.stderr)
        raise SystemExit(1)
    except json.JSONDecodeError as exc:
        print(f"Invalid manifest JSON at {path}: {exc}", file=sys.stderr)
        raise SystemExit(1)


def validate_manifest(manifest: dict) -> None:
    node_keys = {node["key"] for node in manifest.get("nodes", [])}
    if not node_keys:
        print("Manifest contains no nodes.", file=sys.stderr)
        raise SystemExit(1)

    for relationship in manifest.get("relationships", []):
        if relationship["from"] not in node_keys:
            print(f"Relationship source not found: {relationship['from']}", file=sys.stderr)
            raise SystemExit(1)
        if relationship["to"] not in node_keys:
            print(f"Relationship target not found: {relationship['to']}", file=sys.stderr)
            raise SystemExit(1)


def clear_database(tx) -> None:
    tx.run("MATCH (n) DETACH DELETE n")


def merge_node(tx, node: dict) -> None:
    tx.run(
        f"""
        MERGE (n:{node["label"]} {{key: $key}})
        SET n += $properties
        SET n.updated_at = datetime()
        """,
        key=node["key"],
        properties=node.get("properties", {}),
    )


def merge_relationship(tx, relationship: dict) -> None:
    tx.run(
        f"""
        MATCH (a {{key: $from_key}})
        MATCH (b {{key: $to_key}})
        MERGE (a)-[r:{relationship["type"]}]->(b)
        SET r += $properties
        SET r.updated_at = datetime()
        """,
        from_key=relationship["from"],
        to_key=relationship["to"],
        properties=relationship.get("properties", {}),
    )


def create_constraints(tx) -> None:
    tx.run("CREATE CONSTRAINT system_node_key IF NOT EXISTS FOR (n:SystemNode) REQUIRE n.key IS UNIQUE")


def apply_system_label(tx) -> None:
    tx.run("MATCH (n) SET n:SystemNode")


def build_http_base_uri(uri: str) -> str:
    parsed = parse.urlparse(uri)
    if parsed.scheme in {"http", "https"}:
        return uri.rstrip("/")

    if parsed.scheme in {"neo4j+s", "bolt+s", "neo4j+ssc", "bolt+ssc"}:
        return f"https://{parsed.hostname}"

    if parsed.scheme in {"neo4j", "bolt"}:
        if parsed.hostname in {"localhost", "127.0.0.1"}:
            port = 7474
            return f"http://{parsed.hostname}:{port}"
        return f"http://{parsed.hostname}"

    print(f"Unsupported Neo4j URI scheme: {parsed.scheme}", file=sys.stderr)
    raise SystemExit(1)


def run_cypher(base_uri: str, user: str, password: str, database: str, statement: str, parameters: dict | None = None) -> None:
    endpoint = f"{base_uri}/db/{parse.quote(database)}/query/v2"
    payload = json.dumps(
        {
            "statement": statement,
            "parameters": parameters or {},
            "includeCounters": True,
        }
    ).encode("utf-8")
    auth = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
    req = request.Request(
        endpoint,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )

    try:
        with request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        print(f"Neo4j HTTP error: {exc.code} {exc.reason}\n{details}", file=sys.stderr)
        raise SystemExit(1)
    except error.URLError as exc:
        print(f"Neo4j connection error: {exc}", file=sys.stderr)
        raise SystemExit(1)

    if not raw.strip():
        return

    result = json.loads(raw)
    if isinstance(result, dict) and result.get("errors"):
        first_error = result["errors"][0]
        print(f"Neo4j query failed: {first_error.get('code')} {first_error.get('message')}", file=sys.stderr)
        raise SystemExit(1)


def load_graph(config: dict, manifest: dict) -> None:
    base_uri = build_http_base_uri(config["uri"])

    if config["clean"]:
        run_cypher(
            base_uri,
            config["user"],
            config["password"],
            config["database"],
            "MATCH (n) DETACH DELETE n",
        )
    else:
        run_cypher(
            base_uri,
            config["user"],
            config["password"],
            config["database"],
            """
            MATCH (:DeploymentHash)-[r]-()
            DELETE r
            """,
        )
        run_cypher(
            base_uri,
            config["user"],
            config["password"],
            config["database"],
            """
            MATCH (n)-[r:USES_ACTIVE_HASH]->()
            DELETE r
            """,
        )
        run_cypher(
            base_uri,
            config["user"],
            config["password"],
            config["database"],
            """
            MATCH (n:DeploymentHash)
            DETACH DELETE n
            """,
        )

    for node in manifest.get("nodes", []):
        run_cypher(
            base_uri,
            config["user"],
            config["password"],
            config["database"],
            f"""
            MERGE (n:{node["label"]} {{key: $key}})
            SET n += $properties
            SET n.updated_at = datetime()
            """,
            {
                "key": node["key"],
                "properties": node.get("properties", {}),
            },
        )

    run_cypher(
        base_uri,
        config["user"],
        config["password"],
        config["database"],
        "MATCH (n) SET n:SystemNode",
    )
    run_cypher(
        base_uri,
        config["user"],
        config["password"],
        config["database"],
        "CREATE CONSTRAINT system_node_key IF NOT EXISTS FOR (n:SystemNode) REQUIRE n.key IS UNIQUE",
    )

    for relationship in manifest.get("relationships", []):
        run_cypher(
            base_uri,
            config["user"],
            config["password"],
            config["database"],
            f"""
            MATCH (a {{key: $from_key}})
            MATCH (b {{key: $to_key}})
            MERGE (a)-[r:{relationship["type"]}]->(b)
            SET r += $properties
            SET r.updated_at = datetime()
            """,
            {
                "from_key": relationship["from"],
                "to_key": relationship["to"],
                "properties": relationship.get("properties", {}),
            },
        )


def main() -> int:
    config = load_config()
    manifest = load_manifest(config["manifest_path"])
    validate_manifest(manifest)
    load_graph(config, manifest)
    print(
        f"Loaded {len(manifest.get('nodes', []))} nodes and "
        f"{len(manifest.get('relationships', []))} relationships into {config['database']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
