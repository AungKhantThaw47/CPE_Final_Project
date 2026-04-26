import os
import re
import logging
import hashlib
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

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = '''You are an information extraction system. Your task is to read an article that contains one or more <event> ... </event> blocks and extract structured information only from the text inside those blocks.

Follow the instructions below exactly. Generate the extracted information in English only, and do not produce any output based on text outside the <event> tags.

If the article contains:
	•	One <event> ... </event> block → output one JSON object (wrapped in a JSON array).
	•	Two or three <event> ... </event> blocks → output two or three JSON objects in one JSON array.

You must output exactly one JSON object per <event> block.

IMPORTANT OUTPUT RULES:
	•	Return ONLY the JSON array.
	•	Do NOT include explanations, reasoning, or any additional text.
	•	Do NOT use markdown code blocks (no ```json).
	•	Start your response directly with [ and end with ].
	•	No text before [ or after ].
	•	civilian_fatalities and armed_personnel_fatalities must be integers only when provided (not strings).
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
	•	Armed Conflict – Fighting between two or more armed organizations (military, militias, armed groups) in combat over territory, resistance, or control.
	•	Attack – Unilateral violence by armed actors directly targeting civilians.
	•	Airstrike – Explosive or projectile attacks carried out from the air by planes, helicopters, or drones.
	•	Bombing – Ground-based planted or manually delivered explosives.
	•	Fire – Armed organizations deliberately use arson to burn homes, buildings, villages, or vehicles.
	•	Natural disaster – Crises caused by natural forces such as floods, earthquakes, or landslides (not human actors).

⸻
FIELD GUIDELINES
	•	crisis_type – Must be exactly one of the six categories above.
	•	location – Comma-separated address including only the parts that are known, in this order: Township (if known), Region OR State (if known), Country.
Do NOT include districts, villages, street names, or specific landmarks.
Do NOT use "NA" as a placeholder for unknown parts — simply omit them.
If only the country is known, use just the country (e.g., Myanmar).
If only the state is known, use State, Country (e.g., Rakhine State, Myanmar).
Only use "NA" if the location is completely unknown.
Example: Mawlamyine Township, Mon State, Myanmar
	•	date – Use DD/MM/YYYY format (example: 13/03/2023). Do not rely only on explicitly written calendar dates. If the event text uses relative time expressions such as "yesterday", "today", or "last night", convert them into an exact DD/MM/YYYY date by using the article's publication date (the source date) as the reference. If not mentioned anywhere, use "NA".
	•	affected_civilian – "TRUE" if civilians are mentioned as affected (killed, injured, captured), "FALSE" if explicitly stated as not affected, "NA" if not mentioned.
	•	affected_women – "TRUE" if women are mentioned as affected, "FALSE" if explicitly stated as not affected, "NA" if not mentioned.
	•	affected_children – "TRUE" if children are mentioned as affected, "FALSE" if explicitly stated as not affected, "NA" if not mentioned.
	•	civilian_properties_damage – "TRUE" only if civilian-owned properties are damaged (do not count military/armed group facilities). "FALSE" if civilian properties are explicitly not damaged. "NA" if not mentioned.
	•	civilian_forced_displacement – "TRUE" if civilians are explicitly described as fleeing, being evacuated, or forcibly displaced. "FALSE" if explicitly stated that no displacement occurred. "NA" if not mentioned.
	•	civilian_fatalities – Integer count of civilian deaths (e.g., 3). If not clearly stated or not given, use "NA".
	•	armed_personnel_fatalities – Integer count of armed personnel deaths (military, PDF, armed groups). If not clearly stated or not given, use "NA".
	•	number_of_people_displaced – Integer count if explicitly provided; otherwise "NA".
	•	involved_parties –

	INVOLVED PARTIES (CRITICAL RULES):
	This list must include ONLY the organized groups (military, militias, or rebel groups) that are active combatants or primary perpetrators of the event.
	In Armed Conflict: Include all organizations actively fighting each other.
	In Airstrike, Bombing, or Fire: Include only the organization(s) that carried out the action. Don't include other organizations that are victims. Just consider main organization that caused the event.
	Format: A list of strings, e.g., ["Military", "People's Defense Force (PDF)"]. Return [] if none.
	Natural Disaster Rule: If crisis_type is Natural disaster, the involved_parties key must be omitted entirely from the JSON object.

Article:
'''


def build_pipeline_output_hash(source_hash: str, content_hash: str) -> str:
    """Build deterministic folder hash from upstream hash + current content hash."""
    content_hash = (content_hash or "unknown-hash").strip()
    source_hash = (source_hash or "").strip()

    if not source_hash:
        return content_hash

    return hashlib.sha256(f"{source_hash}:{content_hash}".encode("utf-8")).hexdigest()


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
        event_id = build_event_id(source_folder_hash, filename, idx)
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
    
    content_hash = os.environ.get('CONTENT_HASH', 'unknown-hash').strip()
    firestore_collection = os.environ.get('FIRESTORE_COLLECTION', 'events').strip() or 'events'
    
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(crisis_bucket)
        firestore_client = firestore.Client()
        
        # List all files in annotated_articles/
        blobs = bucket.list_blobs(prefix='annotated_articles/')
        
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
                    source_hash = hash_match.group(1)
                    date_str = hash_match.group(2)
                    filename = hash_match.group(3)
                elif legacy_match:
                    source_hash = "legacy"
                    date_str = legacy_match.group(1)
                    filename = legacy_match.group(2)
                else:
                    logger.warning(f"⏭️  Could not parse path: {blob.name}")
                    skipped_count += 1
                    continue
                
                output_hash = build_pipeline_output_hash(source_hash, content_hash)
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
                    continue
                
                # Download and extract
                logger.info(f"📄 Processing: {blob.name}")
                article_text = blob.download_as_text(encoding='utf-8')
                logger.info(f"✅ Downloaded ({len(article_text)} chars)")
                
                logger.info("🤖 Extracting with Gemini...")
                result = extract_events(article_text, gemini_api_key)
                logger.info("✅ Extraction complete")

                events = parse_extracted_events(result)
                
                # Save extracted output
                extracted_blob.upload_from_string(result, content_type='application/json')
                logger.info(f"✅ Saved to gs://{crisis_bucket}/{extracted_blob_name}")

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
