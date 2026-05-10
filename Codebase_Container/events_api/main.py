import os
import sys
from datetime import datetime
from typing import Any, Dict

from flask import Flask, jsonify, request
from google.cloud import firestore

if "/workspace" not in sys.path:
    sys.path.append("/workspace")

from utils.firestore_schema import (
    EVENT_COLLECTION_DEFAULT,
    FIELD_DOCUMENT_NAME,
    FIELD_EVENT_ID,
    FIELD_UPDATED_AT,
    FIELD_USED_FOLDER_HASH,
)

app = Flask(__name__)
app.logger.info("Events API initialized")

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip() or None
COLLECTION = os.environ.get("FIRESTORE_COLLECTION", EVENT_COLLECTION_DEFAULT).strip() or EVENT_COLLECTION_DEFAULT


@app.after_request
def add_cors_headers(response):
    """Allow browser clients (dashboard) to call this API cross-origin."""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Vary"] = "Origin"
    return response


def parse_limit(raw_value: str, default: int = 50, min_value: int = 1, max_value: int = 200) -> int:
    try:
        parsed = int(raw_value)
    except (TypeError, ValueError):
        return default
    return max(min_value, min(max_value, parsed))


def parse_iso_datetime(raw_value: str) -> datetime | None:
    if not raw_value:
        return None
    try:
        # Accept both Z and +00:00 style timestamps.
        normalized = raw_value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


@app.get("/health")
def health() -> Any:
    return jsonify({"status": "ok", "collection": COLLECTION})


@app.get("/events")
def list_events() -> Any:
    limit = parse_limit(request.args.get("limit", "50"))
    folder_hash = request.args.get("folder_hash", "").strip()
    document_name = request.args.get("document_name", "").strip()
    event_id = request.args.get("event_id", "").strip()
    start_after = parse_iso_datetime(request.args.get("start_after", "").strip())

    client = firestore.Client(project=PROJECT_ID)
    query = client.collection(COLLECTION)

    if event_id:
        query = query.where(FIELD_EVENT_ID, "==", event_id)
    if folder_hash:
        query = query.where(FIELD_USED_FOLDER_HASH, "==", folder_hash)
    if document_name:
        query = query.where(FIELD_DOCUMENT_NAME, "==", document_name)

    query = query.order_by(FIELD_UPDATED_AT, direction=firestore.Query.DESCENDING)

    if start_after is not None:
        query = query.where(FIELD_UPDATED_AT, "<", start_after.isoformat())

    docs = query.limit(limit).stream()

    events: list[Dict[str, Any]] = []
    for doc in docs:
        data = doc.to_dict() or {}
        data["id"] = doc.id
        events.append(data)

    return jsonify(
        {
            "count": len(events),
            "limit": limit,
            "filters": {
                "event_id": event_id or None,
                "folder_hash": folder_hash or None,
                "document_name": document_name or None,
                "start_after": request.args.get("start_after", "").strip() or None,
            },
            "events": events,
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
