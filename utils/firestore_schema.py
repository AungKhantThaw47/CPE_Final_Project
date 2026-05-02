"""Shared Firestore schema helpers for event documents."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any, Dict

EVENT_COLLECTION_DEFAULT = "events"

FIELD_EVENT_ID = "event_id"
FIELD_FIRESTORE_DOCUMENT_ID = "firestore_document_id"
FIELD_DOCUMENT_NAME = "document_name"
FIELD_EVENT_INDEX = "event_index"
FIELD_SOURCE_BLOB = "source_blob"
FIELD_SOURCE_FOLDER_HASH = "source_folder_hash"
FIELD_USED_FOLDER_HASH = "used_folder_hash"
FIELD_EVENTS_FOLDER_HASH = "events_folder_hash"
FIELD_OUTPUT_HASH = "output_hash"
FIELD_EVENT_DATE = "event_date"
FIELD_SOURCE_FILENAME = "source_filename"
FIELD_EVENT = "event"
FIELD_UPDATED_AT = "updated_at"


def normalize_id_part(value: str) -> str:
    """Normalize identifier parts for stable Firestore/event IDs."""
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "_", (value or "").strip())
    return cleaned or "unknown"


def build_event_id(output_hash: str, filename: str, event_index: int) -> str:
    """Build event_id as {folder_hash}_{article_id}_{event_index}."""
    article_id = normalize_id_part(os.path.splitext(filename)[0])
    folder_hash_ref = normalize_id_part(output_hash or "legacy")
    return f"{folder_hash_ref}_{article_id}_{event_index}"


def build_event_document(
    *,
    event_id: str,
    filename: str,
    event_index: int,
    source_blob_name: str,
    source_folder_hash: str,
    output_hash: str,
    date_str: str,
    event_payload: Dict[str, Any],
    updated_at_iso: str | None = None,
) -> Dict[str, Any]:
    """Build a Firestore event document using the shared schema."""
    if not updated_at_iso:
        updated_at_iso = datetime.now(timezone.utc).isoformat()

    return {
        FIELD_EVENT_ID: event_id,
        FIELD_FIRESTORE_DOCUMENT_ID: event_id,
        FIELD_DOCUMENT_NAME: filename,
        FIELD_EVENT_INDEX: event_index,
        FIELD_SOURCE_BLOB: source_blob_name,
        FIELD_SOURCE_FOLDER_HASH: source_folder_hash,
        FIELD_USED_FOLDER_HASH: source_folder_hash,
        FIELD_EVENTS_FOLDER_HASH: output_hash,
        FIELD_OUTPUT_HASH: output_hash,
        FIELD_EVENT_DATE: date_str,
        FIELD_SOURCE_FILENAME: filename,
        FIELD_EVENT: event_payload,
        FIELD_UPDATED_AT: updated_at_iso,
    }
