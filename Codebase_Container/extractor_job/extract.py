import os
import re
import logging
import sys
import json
import requests
from datetime import datetime, timezone
from google.cloud import storage
from google.cloud import firestore

if "/workspace" not in sys.path:
    sys.path.append("/workspace")

from utils.firestore_schema import (
    FIELD_EVENT_INDEX,
    FIELD_SOURCE_FILENAME,
    FIELD_USED_FOLDER_HASH,
    build_event_document,
    build_event_id,
)
from utils.neo4j_utils import (
    query_latest_folder_hash_from_neo4j_env,
    query_folder_hash_derived_from_env,
    query_moving_target_hash_from_source_hash_env,
    query_folder_hashes_from_neo4j_env,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = '''You are an information extraction system. Your task is to read an article that contains one or more <event> ... </event> blocks and extract structured information only from the text inside those blocks.

Follow the instructions below exactly and only do what I ask you to do. Generate the extracted information in English only, and do not produce any output based on text outside the <event> tags.

If the article contains:
	•	One <event> ... </event> block → output one JSON object (wrapped in a JSON array).
	•	Two or three <event> ... </event> blocks → output two or three JSON objects in one JSON array.


You must output exactly one JSON object per <event> block.


IMPORTANT OUTPUT RULES:
	•	Return ONLY the raw JSON array. Your entire response must be ONLY the JSON array itself.
	•	Do NOT think out loud. Do NOT write any reasoning, analysis, working steps, bullet points, or notes — not before, not after, not inside the JSON.
	•	Do NOT use markdown code blocks (no ```json or ``` of any kind).
	•	Your response must begin with the character [ and end with the character ]. There must be zero characters before [ and zero characters after ].
	•	Any response that contains text outside the JSON array is incorrect.
	•	civilian_fatalities and non_civilian_fatalities must be integers only when provided (not strings).
	•	number_of_people_displaced must be an integer if provided; otherwise "NA".


SCOPE AND SPECIAL RULES (VERY IMPORTANT)
	1.	The article contains text both inside and outside <event> ... </event> tags.
	2.	You must completely ignore any text outside <event> ... </event> tags.
	•	Treat outside text as if it does not exist.
	•	Do NOT use it to fill missing fields, refine locations, or guess dates.
	3.	Each <event> ... </event> block represents exactly one distinct event.
	•	Output one and only one JSON object for each <event> block.
	•	Do NOT split one <event> block into multiple events.
	•	Do NOT merge multiple <event> blocks into one event.
	4.	If there are multiple <event> blocks, your response must be a single JSON array:
[ {...}, {...}, ... ]

⸻
CRISIS TYPE DEFINITIONS
Use the following rules to decide crisis_type:
	•	Violent_incident → A reported event involving physical harm, use of force, or threat of harm affecting people or locations. This category includes situations where weapons, force or confrntation are described in the text.
	•	Explosion event → A reported event involving an explosion, blast or detonation. This includes any instance where an explosive effect is described, regardless of how it is delivered or characterized.
	•	Fire → Armed organizations deliberately use arson to burn homes, buildings, villages, or vehicles.
	•	Natural disaster → Crises caused by natural forces such as floods, earthquakes, or landslides (not human actors).

⸻
FIELD GUIDELINES
	•	crisis_type → Must be exactly one of the four categories above.
	•	location → Comma-separated address in this order: Township, Region OR State, Country.
Do NOT include districts, villages, street names, or specific landmarks. 
Example: Mawlamyine Township, Mon State, Myanmar
	•	date → Use DD/MM/YYYY format (example: 13/03/2023).Do not rely only on explicitly written calendar dates. If the event text uses relative time expressions such as “yesterday”, “today”, or “last night”, convert them into an exact DD/MM/YYYY date by using the article’s publication date (the source date) as the reference. If not mentioned anywhere, use "NA".
	•	affected_civilian → "TRUE" if civilians are mentioned as affected (killed, injured, captured), "FALSE" if explicitly stated as not affected, "NA" if not mentioned.
	•	affected_women → "TRUE" if women are mentioned as affected, "FALSE" if explicitly stated as not affected, "NA" if not mentioned.
	•	affected_children → "TRUE" if children are mentioned as affected, "FALSE" if explicitly stated as not affected, "NA" if not mentioned.
	•	infrastructure_damage → "TRUE" only if civilian-owned properties are damaged (do not count military/armed group facilities). "FALSE" if civilian properties are explicitly not damaged. "NA" if not mentioned.
	•	displacement → "TRUE"  if civilians are explicitly described as fleeing, being evacuated, or forcibly displaced. "FALSE" if explicitly stated that no displacement occurred. "NA" if not mentioned.
	•	civilian_fatalities → Integer count of civilian deaths (e.g., 3). If not clearly stated or not given, use "NA".
	•	non-civilian_fatalities → Integer count of armed personnel deaths (military, PDF, armed groups). If not clearly stated or not given, use "NA".
	•	number_of_people_displaced → Integer count if explicitly provided; otherwise "NA".
	•	entities → 

	entities (CRITICAL RULES):
	This list must include ONLY the organized groups (military, militias, or rebel groups) that are active combatants or primary perpetrators of the event.
	In Armed Conflict: Include all organizations actively fighting each other.
	In Airstrike, Bombing, or Fire: Include only the organization(s) that carried out the action. Don't include other organizations that are victims. Just consider the main organization that caused the event.
	Format: A list of strings, e.g., ["Military", "People's Defense Force (PDF)"]. Return [] if none.
	Natural Disaster Rule: If crisis_type is Natural disaster, the entity's key must be omitted entirely from the JSON object.

'''


def extract_events(article_text: str, api_key: str) -> str:
    """Extract crisis events from annotated article using Gemini REST API."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={api_key}"

    payload = {
        "contents": [{"parts": [{"text": EXTRACTION_PROMPT + article_text}]}],
        "generationConfig": {"response_mime_type": "application/json"}
    }

    response = requests.post(url, json=payload, headers={"Content-Type": "application/json"})

    if response.status_code == 200:
        result = response.json()
        return result["candidates"][0]["content"]["parts"][0]["text"]
    else:
        raise RuntimeError(f"Gemini API error: {response.status_code} - {response.text}")


def parse_extracted_events(raw_json: str) -> list:
    """Parse extracted events JSON and normalize to a list of dict objects."""
    if not isinstance(raw_json, str):
        raise ValueError("Extraction output is not a string")

    payload = raw_json.strip()
    if payload.startswith("```"):
        payload = re.sub(r"^```(?:json)?\s*", "", payload, flags=re.IGNORECASE)
        payload = re.sub(r"\s*```$", "", payload)

    parsed = json.loads(payload)
    if not isinstance(parsed, list):
        raise ValueError("Extraction output must be a JSON array")

    normalized = []
    for index, item in enumerate(parsed):
        if isinstance(item, dict):
            normalized.append(item)
        else:
            normalized.append({"raw_value": item, "_normalized_index": index})

    return normalized


def write_events_to_firestore(
    firestore_client,
    collection_name: str,
    events: list,
    source_blob_name: str,
    source_folder_hash: str,
    output_hash: str,
    date_str: str,
    filename: str,
) -> int:
    """Upsert extracted events into Firestore and return number of written docs."""
    written = 0
    now_iso = datetime.now(timezone.utc).isoformat()
    collection_ref = firestore_client.collection(collection_name)

    for idx, event in enumerate(events):
        event_id = build_event_id(output_hash, filename, idx)
        doc_id = event_id
        event_payload = event if isinstance(event, dict) else {"raw_value": event}

        # Cleanup legacy IDs for the same event so one event keeps one canonical ID.
        existing_docs = collection_ref.where(FIELD_SOURCE_FILENAME, "==", filename).stream()
        for existing_doc in existing_docs:
            if existing_doc.id == doc_id:
                continue
            existing_data = existing_doc.to_dict() or {}
            if (
                int(existing_data.get(FIELD_EVENT_INDEX, -1)) == idx
                and str(existing_data.get(FIELD_USED_FOLDER_HASH, "")) == str(source_folder_hash)
            ):
                existing_doc.reference.delete()

        doc_data = build_event_document(
            event_id=event_id,
            filename=filename,
            event_index=idx,
            source_blob_name=source_blob_name,
            source_folder_hash=source_folder_hash,
            output_hash=output_hash,
            date_str=date_str,
            event_payload=event_payload,
            updated_at_iso=now_iso,
        )
        # Explicitly delete deprecated field from existing docs on upsert.
        doc_data["source_stage"] = firestore.DELETE_FIELD

        collection_ref.document(doc_id).set(doc_data, merge=True)
        written += 1

    return written


def process_annotated_articles():
    """Batch process all files in annotated_articles/ folder and extract events."""
    logger.info("=" * 60)
    logger.info("BATCH EXTRACTION JOB STARTED")
    logger.info("=" * 60)
    
    crisis_bucket = os.environ.get('CRISIS_BUCKET')
    gemini_api_key = os.environ.get('GEMINI_API_KEY')
    
    if not crisis_bucket or not gemini_api_key:
        logger.error("❌ Missing env vars: CRISIS_BUCKET, GEMINI_API_KEY")
        return False
    
    firestore_collection = os.environ.get('FIRESTORE_COLLECTION', 'events').strip() or 'events'
    
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(crisis_bucket)
        firestore_client = firestore.Client()

        # Emit Neo4j environment and query debug info to help diagnose runtime lookup failures.
        logger.info(
            "Neo4j env: NEO4J_URI=%s, NEO4J_DATABASE=%s, NEO4J_USER=%s, NEO4J_SKIP_SSL_VERIFY=%s",
            os.environ.get("NEO4J_URI"),
            os.environ.get("NEO4J_DATABASE"),
            os.environ.get("NEO4J_USER"),
            os.environ.get("NEO4J_SKIP_SSL_VERIFY"),
        )

        # Connectivity check: use Bolt driver (preferred) to avoid HTTP 403 from HTTP endpoint.
        try:
            neo4j_uri = os.environ.get("NEO4J_URI", "").strip()
            neo4j_user = os.environ.get("NEO4J_USER", "").strip()
            neo4j_password = os.environ.get("NEO4J_PASSWORD", "").strip()
            neo4j_database = os.environ.get("NEO4J_DATABASE", "neo4j").strip() or "neo4j"

            if neo4j_uri and neo4j_user and neo4j_password:
                try:
                    from neo4j import GraphDatabase

                    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
                    with driver.session(database=neo4j_database) as session:
                        rec = session.run("RETURN 1 AS ok").single()
                        ok = rec.get("ok") if rec is not None else None
                        logger.info("Neo4j Bolt check ok=%r", ok)
                except Exception as bolt_exc:
                    logger.warning("Neo4j Bolt check failed: %s", bolt_exc)
        except Exception:
            logger.exception("Unexpected error during Neo4j Bolt debug check")

        # Traverse DERIVED_FROM from the latest pending_review_annotation/ hash to find the matching
        # annotated_articles/ hash. Falls back to the chain tip, then to the newest annotated_articles/
        # hash that actually has GCS content so marker-only tips do not block extraction.
        derived = None
        latest = None
        content_hash = None

        def has_real_article_blob(folder_hash: str) -> bool:
            prefix = f"annotated_articles/{folder_hash}/"
            try:
                for blob in bucket.list_blobs(prefix=prefix):
                    name = blob.name or ""
                    if name.endswith("/") or name.endswith(".FOLDER_CREATED"):
                        continue
                    if name.endswith(".txt"):
                        return True
            except Exception as e:
                logger.warning("Neo4j content fallback GCS probe failed for %s: %s", folder_hash, e)
            return False

        def latest_gcs_annotated_hash_with_content() -> str | None:
            hash_state: dict[str, dict[str, object]] = {}
            try:
                for blob in bucket.list_blobs(prefix="annotated_articles/"):
                    name = blob.name or ""
                    parts = name.split("/")
                    if len(parts) < 2:
                        continue

                    hash_value = parts[1]
                    state = hash_state.setdefault(hash_value, {"latest_updated": None, "has_txt": False})
                    updated = getattr(blob, "updated", None)
                    if updated is not None and (state["latest_updated"] is None or updated > state["latest_updated"]):
                        state["latest_updated"] = updated
                    if name.endswith(".txt"):
                        state["has_txt"] = True
            except Exception as e:
                logger.warning("Annotated_articles GCS scan failed: %s", e)
                return None

            candidates = [
                (hash_value, state["latest_updated"])
                for hash_value, state in hash_state.items()
                if state["has_txt"] and state["latest_updated"] is not None
            ]
            if not candidates:
                return None

            candidates.sort(key=lambda item: item[1], reverse=True)
            return candidates[0][0]

        # Prefer DEPENDS_ON_DATA_FROM resolution: find the annotated_articles/ hash
        # that depends on the latest pending_review_annotation/ hash. This follows
        # the actual data-movement linkage (where articles are moved/assigned)
        # instead of the DERIVED_FROM version-chain path.
        derived = None
        try:
            latest_pending = query_latest_folder_hash_from_neo4j_env("pending_review_annotation/", crisis_bucket)
            logger.info("Neo4j latest pending_review_annotation tip: %r", latest_pending)
            if latest_pending:
                # Ask Neo4j for the mapping regardless of GCS content so we get
                # the recorded DEPENDS_ON_DATA_FROM relationship even when marker
                # files exist. We'll verify content presence separately.
                derived = query_moving_target_hash_from_source_hash_env(
                    source_folder_path="pending_review_annotation/",
                    target_folder_path="annotated_articles/",
                    source_hash=latest_pending,
                )
                # If the mapped target has no real article blobs, ignore it so
                # downstream GCS-aware checks can pick a real contentful hash.
                if derived and not has_real_article_blob(derived):
                    logger.info("DEPENDS_ON result %s has no GCS .txt content; ignoring", derived)
                    derived = None
            logger.info("Neo4j DEPENDS_ON_DATA_FROM query result: %r", derived)
        except Exception as e:
            logger.exception("Neo4j DEPENDS_ON_DATA_FROM query failed: %s", e)

        try:
            latest = query_latest_folder_hash_from_neo4j_env("annotated_articles/", crisis_bucket)
            logger.info("Neo4j chain-tip query result: %r", latest)
        except Exception as e:
            logger.exception("Neo4j chain-tip query failed: %s", e)

        if not derived or not latest:
            try:
                annotated_hashes = query_folder_hashes_from_neo4j_env("annotated_articles/", crisis_bucket)
                for candidate_hash in annotated_hashes:
                    if has_real_article_blob(candidate_hash):
                        content_hash = candidate_hash
                        break
                logger.info("Neo4j content-hash fallback result: %r", content_hash)
                if not content_hash:
                    content_hash = latest_gcs_annotated_hash_with_content()
                    logger.info("GCS content-hash fallback result: %r", content_hash)
            except Exception as e:
                logger.exception("Neo4j content-hash fallback query failed: %s", e)

        source_hash = (derived or latest or content_hash or "")
        if not source_hash:
            logger.error("❌ No annotated_articles/ hash found in Neo4j (via DERIVED_FROM or chain tip)")
            return False

        logger.info(f"🔎 Neo4j source hash: {source_hash}")

        # events/ output hash mirrors the annotated_articles/ source hash for version isolation
        output_hash = source_hash

        # List only the latest annotated batch resolved from Neo4j.
        blobs = bucket.list_blobs(prefix=f'annotated_articles/{source_hash}/')
        
        processed_count = 0
        skipped_count = 0
        error_count = 0
        
        for blob in blobs:
            # Skip directories and non-txt files
            if blob.name.endswith('/') or not blob.name.endswith('.txt'):
                continue
            
            try:
                # Parse source path
                # hashed: annotated_articles/{hash}/{date}/{filename}
                # legacy: annotated_articles/{date}/{filename}
                hash_match = re.match(r'annotated_articles/([^/]+)/(\d{4}-\d{2}-\d{2})/(.+\.txt)$', blob.name)
                legacy_match = re.match(r'annotated_articles/(\d{4}-\d{2}-\d{2})/(.+\.txt)$', blob.name)
                
                if hash_match:
                    blob_hash = hash_match.group(1)
                    date_str = hash_match.group(2)
                    filename = hash_match.group(3)
                elif legacy_match:
                    blob_hash = source_hash
                    date_str = legacy_match.group(1)
                    filename = legacy_match.group(2)
                else:
                    logger.warning(f"⏭️  Could not parse path: {blob.name}")
                    skipped_count += 1
                    continue

                if blob_hash != source_hash:
                    logger.warning(
                        "⚠️  Blob hash %s does not match Neo4j source hash %s; skipping %s",
                        blob_hash,
                        source_hash,
                        blob.name,
                    )
                    skipped_count += 1
                    continue
                
                output_filename = filename.replace('.txt', '.json')
                extracted_blob_name = f"events/{output_hash}/{date_str}/{output_filename}"
                
                # Check if already extracted
                extracted_blob = bucket.blob(extracted_blob_name)
                if extracted_blob.exists():
                    logger.info(f"⏭️  Already extracted: {extracted_blob_name}")

                    try:
                        existing_result = extracted_blob.download_as_text(encoding='utf-8')
                        existing_events = parse_extracted_events(existing_result)
                        firestore_written = write_events_to_firestore(
                            firestore_client=firestore_client,
                            collection_name=firestore_collection,
                            events=existing_events,
                            source_blob_name=blob.name,
                            source_folder_hash=source_hash,
                            output_hash=output_hash,
                            date_str=date_str,
                            filename=filename,
                        )
                        logger.info(f"✅ Synced {firestore_written} existing event document(s) to Firestore collection '{firestore_collection}'")
                    except Exception as firestore_sync_error:
                        logger.warning(f"⚠️  Firestore sync for existing output failed: {firestore_sync_error}")

                    skipped_count += 1
                    blob.delete()
                    logger.info(f"🗑️  Deleted source: {blob.name}")
                    continue

                # Download and extract
                logger.info(f"📄 Processing: {blob.name}")
                article_text = blob.download_as_text(encoding='utf-8')
                logger.info(f"✅ Downloaded ({len(article_text)} chars)")

                logger.info("🤖 Extracting with Gemini...")
                result = extract_events(article_text, gemini_api_key)
                logger.info("✅ Extraction complete")

                events = parse_extracted_events(result)

                # Save extracted output, then remove source
                extracted_blob.upload_from_string(result, content_type='application/json')
                logger.info(f"✅ Saved to gs://{crisis_bucket}/{extracted_blob_name}")
                blob.delete()
                logger.info(f"🗑️  Deleted source: {blob.name}")

                firestore_written = write_events_to_firestore(
                    firestore_client=firestore_client,
                    collection_name=firestore_collection,
                    events=events,
                    source_blob_name=blob.name,
                    source_folder_hash=source_hash,
                    output_hash=output_hash,
                    date_str=date_str,
                    filename=filename,
                )
                logger.info(f"✅ Upserted {firestore_written} event document(s) to Firestore collection '{firestore_collection}'")

                processed_count += 1
                
            except Exception as e:
                logger.error(f"❌ Error processing {blob.name}: {e}")
                error_count += 1
                continue
        
        logger.info("=" * 60)
        logger.info(f"BATCH COMPLETE: {processed_count} processed, {skipped_count} skipped, {error_count} errors")
        logger.info("=" * 60)
        
        return error_count == 0
    
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = process_annotated_articles()
    sys.exit(0 if success else 1)
