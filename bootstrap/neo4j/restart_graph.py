#!/usr/bin/env python3

import os

import load_graph


def main() -> int:
    # Force full graph reset so historical nodes/relationships are removed.
    os.environ["NEO4J_CLEAN"] = "true"

    config = load_graph.load_config()
    config["clean"] = True

    manifest = load_graph.load_manifest(config["manifest_path"])
    load_graph.validate_manifest(manifest)
    load_graph.load_graph(config, manifest)

    print(
        f"Restarted graph in database '{config['database']}' with clean reload "
        f"from {config['manifest_path']} ({len(manifest.get('nodes', []))} nodes, "
        f"{len(manifest.get('relationships', []))} relationships)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
